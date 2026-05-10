package com.ace.platform.payment;

import com.ace.platform.conversation.ConversationRole;
import com.ace.platform.conversation.ConversationService;
import com.ace.platform.events.LeadEventService;
import com.ace.platform.lead.Lead;
import com.ace.platform.lead.LeadService;
import org.springframework.boot.autoconfigure.condition.ConditionalOnBean;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Controller;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.ResponseBody;
import org.springframework.web.server.ResponseStatusException;
import org.springframework.web.servlet.view.RedirectView;

import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.Map;

@Controller
@ConditionalOnBean(PaymentService.class)
public class PublicPaymentController {

    private final PaymentService paymentService;
    private final LeadService leadService;
    private final ConversationService conversationService;
    private final LeadEventService leadEventService;

    public PublicPaymentController(
        PaymentService paymentService,
        LeadService leadService,
        ConversationService conversationService,
        LeadEventService leadEventService
    ) {
        this.paymentService = paymentService;
        this.leadService = leadService;
        this.conversationService = conversationService;
        this.leadEventService = leadEventService;
    }

    @GetMapping(value = "/pay/{publicToken}", produces = MediaType.TEXT_HTML_VALUE)
    @ResponseBody
    public Object publicPaymentPage(@PathVariable String publicToken) {
        PaymentRequest paymentRequest = paymentService.getByPublicToken(publicToken)
            .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Payment request not found"));

        if ("paid".equals(paymentRequest.getStatus())) {
            return page("Plačilo prejeto", "<h1 class='ok'>Plačilo uspešno prejeto</h1><p class='amount'>" + money(paymentRequest) + "</p><p>Hvala. Vaše plačilo za <strong>" + escape(paymentRequest.getPurpose()) + "</strong> je bilo uspešno evidentirano.</p>");
        }

        if (paymentRequest.getPaymentUrl() != null && paymentRequest.getPaymentUrl().startsWith("http")) {
            return new RedirectView(paymentRequest.getPaymentUrl());
        }

        boolean expired = paymentRequest.getExpiresAt() != null && paymentRequest.getExpiresAt().isBefore(Instant.now());
        if (expired) {
            return page("Zahtevek je potekel", "<h1 class='warn'>Ta zahtevek je potekel</h1><p class='amount'>" + money(paymentRequest) + "</p><p class='muted'>" + escape(paymentRequest.getPurpose()) + "</p>");
        }

        String note = paymentRequest.getNote() != null && !paymentRequest.getNote().isBlank()
            ? "<div class='note'>" + escape(paymentRequest.getNote()) + "</div>"
            : "";
        return page(
            "Plačilo",
            "<h1>Plačilo</h1>"
                + "<p class='muted'>" + escape(paymentRequest.getPurpose()) + "</p>"
                + "<div class='amount'>" + money(paymentRequest) + "</div>"
                + note
                + "<p class='muted'>To je lokalni demo plačilni zaslon. V produkciji ga lahko nadomesti Stripe Checkout.</p>"
                + "<form method='post' action='/pay/" + paymentRequest.getPublicToken() + "/complete'>"
                + "<button class='btn' type='submit'>Potrdi plačilo</button>"
                + "</form>"
        );
    }

    @PostMapping("/pay/{publicToken}/complete")
    @Transactional
    public RedirectView completePublicPayment(@PathVariable String publicToken) {
        PaymentRequest paymentRequest = paymentService.getByPublicToken(publicToken)
            .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Payment request not found"));
        paymentRequest = paymentService.markPaid(paymentRequest, null, null, null);
        publishPaid(paymentRequest);
        return new RedirectView("/pay/" + publicToken, true);
    }

    @GetMapping(value = "/pay/success", produces = MediaType.TEXT_HTML_VALUE)
    @ResponseBody
    @Transactional
    public Object stripeSuccessPage(@RequestParam("payment_request_id") Long paymentRequestId, @RequestParam("session_id") String sessionId) {
        PaymentRequest paymentRequest = paymentService.getRequestById(paymentRequestId)
            .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Payment request not found"));

        String stripeAccountId = null;
        if (paymentRequest.getProviderPayload() != null && paymentRequest.getProviderPayload().get("stripe_account_id") != null) {
            stripeAccountId = String.valueOf(paymentRequest.getProviderPayload().get("stripe_account_id"));
        }
        Map<String, Object> data = paymentService.verifyStripeCheckout(sessionId, stripeAccountId);
        if (data != null && "paid".equals(String.valueOf(data.get("payment_status")))) {
            paymentRequest = paymentService.markPaid(
                paymentRequest,
                string(data.get("payment_intent")),
                string(data.get("id")),
                Map.of("stripe_session", data)
            );
            publishPaid(paymentRequest);
            return page("Plačilo uspešno", "<h1 class='ok'>Plačilo uspešno</h1><p class='amount'>" + money(paymentRequest) + "</p><p>Vaše plačilo je bilo potrjeno.</p>");
        }
        return page("Plačilo v obdelavi", "<h1>Plačilo je še v obdelavi</h1><p>Če je bilo plačilo uspešno, se bo status v sistemu posodobil kmalu.</p>");
    }

    @GetMapping(value = "/pay/cancel", produces = MediaType.TEXT_HTML_VALUE)
    @ResponseBody
    public Object stripeCancelPage(@RequestParam("payment_request_id") Long paymentRequestId) {
        return page("Plačilo preklicano", "<h1 class='warn'>Plačilo ni bilo dokončano</h1><p>Lahko se vrnete v pogovor in poskusite znova.</p>");
    }

    @GetMapping("/api/public/payments/stripe/connect/callback")
    @Transactional
    public RedirectView stripeConnectCallback(
        @RequestParam(required = false) String code,
        @RequestParam(required = false) String state,
        @RequestParam(required = false) String error,
        @RequestParam(name = "error_description", required = false) String errorDescription
    ) {
        if (error != null) {
            OrganizationPaymentSettings settings = paymentService.markConnectError(state, errorDescription != null ? errorDescription : error).orElse(null);
            return redirectToDashboard(settings, "error", errorDescription != null ? errorDescription : error);
        }
        if (code == null || state == null) {
            return new RedirectView("/?stripe=error&message=" + encode("Missing Stripe callback parameters"));
        }
        try {
            OrganizationPaymentSettings settings = paymentService.handleConnectCallback(state, code);
            return redirectToDashboard(settings, "connected", null);
        } catch (Exception ex) {
            OrganizationPaymentSettings settings = paymentService.markConnectError(state, ex.getMessage()).orElse(null);
            return redirectToDashboard(settings, "error", ex.getMessage());
        }
    }

    private RedirectView redirectToDashboard(OrganizationPaymentSettings settings, String status, String message) {
        String target = settings != null
            ? paymentService.dashboardUrlForOrganization(settings.getOrganization().getSlug())
            : "/?tab=payments";
        String separator = target.contains("?") ? "&" : "?";
        target += separator + "stripe=" + encode(status);
        if (message != null && !message.isBlank()) {
            target += "&message=" + encode(message);
        }
        return new RedirectView(target);
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

    private String money(PaymentRequest paymentRequest) {
        return String.format(java.util.Locale.US, "%.2f %s", paymentRequest.getAmountCents() / 100.0, paymentRequest.getCurrency().toUpperCase());
    }

    private String string(Object value) {
        return value != null ? String.valueOf(value) : null;
    }

    private String encode(String value) {
        return URLEncoder.encode(value != null ? value : "", StandardCharsets.UTF_8);
    }

    private String escape(String value) {
        return value == null ? "" : value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;");
    }

    private ResponseEntity<String> page(String title, String body) {
        String html = "<!doctype html>"
            + "<html lang='sl'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
            + "<title>" + title + "</title>"
            + "<style>"
            + "body { font-family: system-ui, sans-serif; background:#f3f4f6; margin:0; padding:32px; color:#111827; }"
            + ".card { max-width:640px; margin:0 auto; background:#fff; border-radius:16px; padding:24px; box-shadow:0 10px 30px rgba(0,0,0,.08); }"
            + "h1 { margin-top:0; font-size:28px; }"
            + ".amount { font-size:34px; font-weight:800; margin:10px 0 18px; }"
            + ".muted { color:#6b7280; }"
            + ".note { background:#f9fafb; border:1px solid #e5e7eb; border-radius:12px; padding:12px 14px; margin:16px 0; }"
            + ".btn { display:inline-block; background:#2563eb; color:#fff; border:none; border-radius:10px; padding:12px 18px; font-weight:700; text-decoration:none; cursor:pointer; }"
            + ".ok { color:#166534; }"
            + ".warn { color:#92400e; }"
            + "</style></head><body><div class='card'>" + body + "</div></body></html>";
        return ResponseEntity.ok().contentType(MediaType.TEXT_HTML).body(html);
    }
}
