package com.ace.platform.payment;

import com.ace.platform.conversation.ConversationRole;
import com.ace.platform.conversation.ConversationService;
import com.ace.platform.events.LeadEventService;
import com.ace.platform.lead.Lead;
import com.ace.platform.lead.LeadService;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.autoconfigure.condition.ConditionalOnBean;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.HexFormat;
import java.util.LinkedHashMap;
import java.util.Map;

@RestController
@ConditionalOnBean(PaymentService.class)
public class StripeWebhookController {

    private final PaymentService paymentService;
    private final LeadService leadService;
    private final ConversationService conversationService;
    private final LeadEventService leadEventService;
    private final ObjectMapper objectMapper;
    private final String stripeWebhookSecret;

    public StripeWebhookController(
        PaymentService paymentService,
        LeadService leadService,
        ConversationService conversationService,
        LeadEventService leadEventService,
        ObjectMapper objectMapper,
        @Value("${STRIPE_WEBHOOK_SECRET:}") String stripeWebhookSecret
    ) {
        this.paymentService = paymentService;
        this.leadService = leadService;
        this.conversationService = conversationService;
        this.leadEventService = leadEventService;
        this.objectMapper = objectMapper;
        this.stripeWebhookSecret = stripeWebhookSecret != null ? stripeWebhookSecret.trim() : "";
    }

    @PostMapping("/api/payments/webhooks/stripe")
    public Map<String, Object> stripeWebhook(
        @RequestBody byte[] payload,
        @RequestHeader(name = "Stripe-Signature", required = false) String stripeSignature
    ) {
        if (!verifySignature(payload, stripeSignature)) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Invalid Stripe signature");
        }

        try {
            Map<String, Object> event = objectMapper.readValue(payload, new TypeReference<>() {});
            String eventType = string(event.get("type"));
            Map<String, Object> data = nestedMap(event, "data", "object");

            if ("account.updated".equals(eventType)) {
                String stripeAccountId = string(data.get("id"));
                if (stripeAccountId != null) {
                    paymentService.findSettingsByStripeAccountId(stripeAccountId).ifPresent(settings -> paymentService.refreshConnectStatus(settings));
                }
                return Map.of("ok", true);
            }

            if ("checkout.session.completed".equals(eventType)) {
                Map<String, Object> metadata = nestedMap(data, "metadata");
                String paymentRequestId = string(metadata.get("payment_request_id"));
                if (paymentRequestId == null) {
                    paymentRequestId = string(data.get("client_reference_id"));
                }
                if (paymentRequestId != null) {
                    paymentService.getRequestById(Long.valueOf(paymentRequestId)).ifPresent(paymentRequest -> {
                        PaymentRequest updated = paymentService.markPaid(
                            paymentRequest,
                            string(data.get("payment_intent")),
                            string(data.get("id")),
                            Map.of("stripe_session", data)
                        );
                        publishPaid(updated);
                    });
                }
                return Map.of("ok", true);
            }

            return Map.of("ok", true, "ignored", eventType);
        } catch (Exception ex) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Invalid webhook payload");
        }
    }

    private void publishPaid(PaymentRequest paymentRequest) {
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("id", paymentRequest.getId());
        payload.put("status", paymentRequest.getStatus());
        payload.put("amountCents", paymentRequest.getAmountCents());
        payload.put("currency", paymentRequest.getCurrency());
        payload.put("purpose", paymentRequest.getPurpose());
        payload.put("paidAt", paymentRequest.getPaidAt() != null ? paymentRequest.getPaidAt().toString() : null);
        leadEventService.publish(paymentRequest.getOrganization(), paymentRequest.getSid(), "payment.request.paid", payload);
        Lead lead = leadService.findByOrganizationAndSid(paymentRequest.getOrganization().getId(), paymentRequest.getSid())
            .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Lead not found"));
        conversationService.appendMessage(lead, ConversationRole.ASSISTANT, "Plačilo uspešno prejeto za: " + paymentRequest.getPurpose() + ".");
    }

    private boolean verifySignature(byte[] payload, String stripeSignature) {
        if (stripeWebhookSecret.isBlank() || stripeSignature == null || stripeSignature.isBlank()) {
            return false;
        }
        try {
            Map<String, String> parts = new LinkedHashMap<>();
            for (String part : stripeSignature.split(",")) {
                String[] kv = part.split("=", 2);
                if (kv.length == 2) parts.put(kv[0], kv[1]);
            }
            String timestamp = parts.get("t");
            String signature = parts.get("v1");
            if (timestamp == null || signature == null) return false;
            long ts = Long.parseLong(timestamp);
            if (Math.abs(Instant.now().getEpochSecond() - ts) > 300) return false;
            Mac mac = Mac.getInstance("HmacSHA256");
            mac.init(new SecretKeySpec(stripeWebhookSecret.getBytes(StandardCharsets.UTF_8), "HmacSHA256"));
            byte[] digest = mac.doFinal((timestamp + "." + new String(payload, StandardCharsets.UTF_8)).getBytes(StandardCharsets.UTF_8));
            String expected = HexFormat.of().formatHex(digest);
            return expected.equals(signature);
        } catch (Exception ex) {
            return false;
        }
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> nestedMap(Map<String, Object> root, String... path) {
        Object current = root;
        for (String key : path) {
            if (!(current instanceof Map<?, ?> map)) return Map.of();
            current = map.get(key);
        }
        return current instanceof Map<?, ?> map ? (Map<String, Object>) map : Map.of();
    }

    private String string(Object value) {
        return value != null ? String.valueOf(value) : null;
    }
}
