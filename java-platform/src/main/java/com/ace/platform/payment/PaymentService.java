package com.ace.platform.payment;

import com.ace.platform.organization.Organization;
import com.ace.platform.organization.OrganizationRepository;
import com.ace.platform.user.User;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.data.domain.PageRequest;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.io.IOException;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.net.URI;
import java.net.URLEncoder;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.security.SecureRandom;
import java.time.Duration;
import java.time.Instant;
import java.util.Base64;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;

@Service
@ConditionalOnProperty(name = "ace.payments.enabled", havingValue = "true", matchIfMissing = true)
public class PaymentService {

    private final OrganizationRepository organizationRepository;
    private final OrganizationPaymentSettingsRepository settingsRepository;
    private final PaymentRequestRepository paymentRequestRepository;
    private final ObjectMapper objectMapper;
    private final HttpClient httpClient;
    private final SecureRandom secureRandom = new SecureRandom();
    private final String fallbackProvider;
    private final String publicBaseUrl;
    private final String stripeSecretKey;
    private final String stripeConnectClientId;

    public PaymentService(
        OrganizationRepository organizationRepository,
        OrganizationPaymentSettingsRepository settingsRepository,
        PaymentRequestRepository paymentRequestRepository,
        ObjectMapper objectMapper,
        @Value("${ACE_PAYMENT_PROVIDER:mock}") String fallbackProvider,
        @Value("${ACE_PUBLIC_BASE_URL:http://localhost:8080}") String publicBaseUrl,
        @Value("${STRIPE_SECRET_KEY:}") String stripeSecretKey,
        @Value("${STRIPE_CONNECT_CLIENT_ID:}") String stripeConnectClientId
    ) {
        this.organizationRepository = organizationRepository;
        this.settingsRepository = settingsRepository;
        this.paymentRequestRepository = paymentRequestRepository;
        this.objectMapper = objectMapper;
        this.fallbackProvider = fallbackProvider != null ? fallbackProvider.trim().toLowerCase() : "mock";
        this.publicBaseUrl = stripTrailingSlash(publicBaseUrl != null ? publicBaseUrl.trim() : "http://localhost:8080");
        this.stripeSecretKey = stripeSecretKey != null ? stripeSecretKey.trim() : "";
        this.stripeConnectClientId = stripeConnectClientId != null ? stripeConnectClientId.trim() : "";
        this.httpClient = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(10)).build();
    }

    @Transactional
    public OrganizationPaymentSettings getOrCreateSettings(Long organizationId) {
        return settingsRepository.findByOrganizationId(organizationId)
            .orElseGet(() -> {
                Organization organization = organizationRepository.findById(organizationId)
                    .orElseThrow(() -> new IllegalArgumentException("Organization not found"));
                OrganizationPaymentSettings settings = new OrganizationPaymentSettings(organization);
                settings.setProvider("stripe");
                settings.setMode("stripe_connect_standard");
                settings.setPaymentsEnabled(false);
                settings.setDefaultCurrency("EUR");
                settings.setStripeConnectStatus("not_connected");
                return settingsRepository.save(settings);
            });
    }

    @Transactional
    public OrganizationPaymentSettings refreshConnectStatus(OrganizationPaymentSettings settings) {
        if (blank(settings.getStripeAccountId()) || blank(stripeSecretKey)) {
            settings.setPaymentsEnabled(false);
            settings.setStripeConnectStatus("not_connected");
            settings.setLastSyncedAt(Instant.now());
            return settingsRepository.save(settings);
        }

        Map<String, Object> account = stripeGet("https://api.stripe.com/v1/accounts/" + encode(settings.getStripeAccountId()), null);
        settings.setStripeOnboardingComplete(bool(account.get("details_submitted")));
        settings.setStripeDetailsSubmitted(bool(account.get("details_submitted")));
        settings.setStripeChargesEnabled(bool(account.get("charges_enabled")));
        settings.setStripePayoutsEnabled(bool(account.get("payouts_enabled")));
        settings.setStripeLivemode(bool(account.get("livemode")));
        settings.setStripeLastError(null);
        settings.setLastSyncedAt(Instant.now());
        settings.setPaymentsEnabled(settings.isStripeChargesEnabled());
        settings.setStripeConnectStatus(settings.isPaymentsEnabled() ? "connected" : "restricted");
        return settingsRepository.save(settings);
    }

    @Transactional
    public String createConnectLink(Long organizationId) {
        if (blank(stripeConnectClientId)) {
            throw new IllegalStateException("Missing STRIPE_CONNECT_CLIENT_ID");
        }
        OrganizationPaymentSettings settings = getOrCreateSettings(organizationId);
        String state = token(24);
        settings.setStripeOauthState(state);
        settings.setStripeConnectStatus("pending");
        settings.setStripeLastError(null);
        settingsRepository.save(settings);

        Map<String, String> params = new LinkedHashMap<>();
        params.put("response_type", "code");
        params.put("client_id", stripeConnectClientId);
        params.put("scope", "read_write");
        params.put("state", state);
        params.put("redirect_uri", publicBaseUrl + "/api/public/payments/stripe/connect/callback");
        params.put("suggested_capabilities[]", "transfers");
        params.put("stripe_user[business_type]", "company");
        return "https://connect.stripe.com/oauth/authorize?" + formEncode(params);
    }

    @Transactional
    public OrganizationPaymentSettings handleConnectCallback(String state, String code) {
        OrganizationPaymentSettings settings = settingsRepository.findByStripeOauthState(state)
            .orElseThrow(() -> new IllegalArgumentException("Invalid or expired Stripe connect state"));
        if (blank(stripeSecretKey)) {
            throw new IllegalStateException("Missing STRIPE_SECRET_KEY");
        }

        Map<String, String> form = new LinkedHashMap<>();
        form.put("grant_type", "authorization_code");
        form.put("code", code);
        Map<String, Object> data = stripePost("https://connect.stripe.com/oauth/token", form, null);

        settings.setStripeAccountId(string(data.get("stripe_user_id")));
        settings.setStripeAccessToken(string(data.get("access_token")));
        settings.setStripeRefreshToken(string(data.get("refresh_token")));
        settings.setStripePublishableKey(string(data.get("stripe_publishable_key")));
        settings.setStripeScope(string(data.get("scope")));
        settings.setStripeLivemode(bool(data.get("livemode")));
        settings.setStripeOauthState(null);
        settings.setStripeLastError(null);
        settingsRepository.save(settings);
        return refreshConnectStatus(settings);
    }

    @Transactional
    public Optional<OrganizationPaymentSettings> markConnectError(String state, String errorMessage) {
        if (blank(state)) return Optional.empty();
        return settingsRepository.findByStripeOauthState(state).map(settings -> {
            settings.setStripeConnectStatus("error");
            settings.setStripeLastError(truncate(errorMessage, 1000));
            settings.setStripeOauthState(null);
            settings.setPaymentsEnabled(false);
            settings.setLastSyncedAt(Instant.now());
            return settingsRepository.save(settings);
        });
    }

    @Transactional
    public PaymentRequest createPaymentRequest(
        Long organizationId,
        String sid,
        User createdByUser,
        Double amount,
        String currency,
        String purpose,
        String note,
        Integer expiresInHours
    ) {
        Organization organization = organizationRepository.findById(organizationId)
            .orElseThrow(() -> new IllegalArgumentException("Organization not found"));
        OrganizationPaymentSettings settings = getOrCreateSettings(organizationId);

        int amountCents = amountToCents(amount);
        String currencyNorm = !blank(currency) ? currency.trim().toUpperCase() : settings.getDefaultCurrency();
        String purposeNorm = !blank(purpose) ? purpose.trim() : "Payment request";
        String noteNorm = note != null ? note.trim() : "";

        PaymentRequest paymentRequest = new PaymentRequest(
            organization,
            createdByUser,
            sid,
            token(18),
            amountCents,
            currencyNorm,
            purposeNorm,
            noteNorm
        );
        paymentRequest.setProvider(resolveProvider(settings));
        paymentRequest.setStatus("draft");
        if (expiresInHours != null && expiresInHours > 0) {
            paymentRequest.setExpiresAt(Instant.now().plus(Duration.ofHours(expiresInHours)));
        }
        paymentRequest = paymentRequestRepository.save(paymentRequest);

        CreatedPaymentLink link = buildLink(paymentRequest, settings);
        paymentRequest.setProvider(link.provider());
        paymentRequest.setPaymentUrl(link.paymentUrl());
        paymentRequest.setProviderPaymentId(link.providerPaymentId());
        paymentRequest.setProviderSessionId(link.providerSessionId());
        paymentRequest.setProviderPayload(link.providerPayload());
        paymentRequest.setStatus("sent");
        return paymentRequestRepository.save(paymentRequest);
    }

    @Transactional(readOnly = true)
    public List<PaymentRequest> listRequests(Long organizationId, String sid, int limit) {
        PageRequest page = PageRequest.of(0, Math.max(1, Math.min(limit, 500)));
        if (blank(sid)) {
            return paymentRequestRepository.findByOrganizationIdOrderByCreatedAtDesc(organizationId, page);
        }
        return paymentRequestRepository.findByOrganizationIdAndSidOrderByCreatedAtDesc(organizationId, sid, page);
    }

    @Transactional(readOnly = true)
    public Optional<PaymentRequest> getById(Long organizationId, Long requestId) {
        return paymentRequestRepository.findByOrganizationIdAndId(organizationId, requestId);
    }

    @Transactional(readOnly = true)
    public Optional<PaymentRequest> getRequestById(Long requestId) {
        return paymentRequestRepository.findById(requestId);
    }

    @Transactional(readOnly = true)
    public Optional<PaymentRequest> getByPublicToken(String publicToken) {
        return paymentRequestRepository.findByPublicToken(publicToken);
    }

    @Transactional(readOnly = true)
    public Optional<OrganizationPaymentSettings> findSettingsByStripeAccountId(String stripeAccountId) {
        return settingsRepository.findByStripeAccountId(stripeAccountId);
    }

    @Transactional
    public PaymentRequest markPaid(PaymentRequest paymentRequest, String providerPaymentId, String providerSessionId, Map<String, Object> providerPayload) {
        if ("paid".equals(paymentRequest.getStatus())) {
            return paymentRequest;
        }
        paymentRequest.setStatus("paid");
        paymentRequest.setPaidAt(Instant.now());
        if (!blank(providerPaymentId)) paymentRequest.setProviderPaymentId(providerPaymentId);
        if (!blank(providerSessionId)) paymentRequest.setProviderSessionId(providerSessionId);
        if (providerPayload != null && !providerPayload.isEmpty()) paymentRequest.setProviderPayload(providerPayload);
        return paymentRequestRepository.save(paymentRequest);
    }

    @Transactional
    public PaymentRequest markCancelled(PaymentRequest paymentRequest) {
        if ("paid".equals(paymentRequest.getStatus())) {
            return paymentRequest;
        }
        paymentRequest.setStatus("cancelled");
        return paymentRequestRepository.save(paymentRequest);
    }

    @Transactional(readOnly = true)
    public Map<String, Object> verifyStripeCheckout(String sessionId, String stripeAccountId) {
        if (blank(stripeSecretKey) || blank(sessionId)) {
            return null;
        }
        return stripeGet("https://api.stripe.com/v1/checkout/sessions/" + encode(sessionId), blank(stripeAccountId) ? null : Map.of("Stripe-Account", stripeAccountId));
    }

    public Map<String, Object> toSettingsPayload(OrganizationPaymentSettings settings) {
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("id", settings.getId());
        out.put("organization_id", settings.getOrganization().getId());
        out.put("provider", settings.getProvider());
        out.put("mode", settings.getMode());
        out.put("payments_enabled", settings.isPaymentsEnabled());
        out.put("default_currency", settings.getDefaultCurrency());
        out.put("stripe_account_id", settings.getStripeAccountId());
        out.put("stripe_connect_status", settings.getStripeConnectStatus());
        out.put("stripe_onboarding_complete", settings.isStripeOnboardingComplete());
        out.put("stripe_details_submitted", settings.isStripeDetailsSubmitted());
        out.put("stripe_charges_enabled", settings.isStripeChargesEnabled());
        out.put("stripe_payouts_enabled", settings.isStripePayoutsEnabled());
        out.put("stripe_publishable_key", settings.getStripePublishableKey());
        out.put("stripe_scope", settings.getStripeScope());
        out.put("stripe_livemode", settings.isStripeLivemode());
        out.put("stripe_last_error", settings.getStripeLastError());
        out.put("last_synced_at", settings.getLastSyncedAt() != null ? settings.getLastSyncedAt().toString() : null);
        out.put("created_at", settings.getCreatedAt() != null ? settings.getCreatedAt().toString() : null);
        out.put("updated_at", settings.getUpdatedAt() != null ? settings.getUpdatedAt().toString() : null);
        return out;
    }

    public Map<String, Object> toPaymentRequestPayload(PaymentRequest item) {
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("id", item.getId());
        out.put("organization_id", item.getOrganization().getId());
        out.put("sid", item.getSid());
        out.put("created_by_user_id", item.getCreatedByUser() != null ? item.getCreatedByUser().getId() : null);
        out.put("provider", item.getProvider());
        out.put("provider_payment_id", item.getProviderPaymentId());
        out.put("provider_session_id", item.getProviderSessionId());
        out.put("public_token", item.getPublicToken());
        out.put("amount_cents", item.getAmountCents());
        out.put("currency", item.getCurrency());
        out.put("purpose", item.getPurpose());
        out.put("note", item.getNote());
        out.put("status", item.getStatus());
        out.put("payment_url", item.getPaymentUrl());
        out.put("expires_at", item.getExpiresAt() != null ? item.getExpiresAt().toString() : null);
        out.put("paid_at", item.getPaidAt() != null ? item.getPaidAt().toString() : null);
        out.put("provider_payload", item.getProviderPayload() != null ? item.getProviderPayload() : Map.of());
        out.put("created_at", item.getCreatedAt() != null ? item.getCreatedAt().toString() : null);
        out.put("updated_at", item.getUpdatedAt() != null ? item.getUpdatedAt().toString() : null);
        return out;
    }

    public String dashboardUrlForOrganization(String orgSlug) {
        return "/" + orgSlug + "/dashboard?tab=payments";
    }

    private String resolveProvider(OrganizationPaymentSettings settings) {
        if (!blank(settings.getStripeAccountId()) && settings.isPaymentsEnabled() && !blank(stripeSecretKey)) {
            return "stripe_connect";
        }
        if (!blank(stripeSecretKey)) {
            return "stripe_demo";
        }
        return "mock".equals(fallbackProvider) ? "mock" : "mock";
    }

    private CreatedPaymentLink buildLink(PaymentRequest paymentRequest, OrganizationPaymentSettings settings) {
        if ("stripe_connect".equals(paymentRequest.getProvider()) && !blank(stripeSecretKey) && !blank(settings.getStripeAccountId())) {
            try {
                return createStripeCheckout(paymentRequest, settings.getStripeAccountId());
            } catch (RuntimeException ex) {
                settings.setStripeLastError(truncate(ex.getMessage(), 1000));
                settings.setStripeConnectStatus("error");
                settings.setPaymentsEnabled(false);
                settings.setLastSyncedAt(Instant.now());
                settingsRepository.save(settings);
                throw ex;
            }
        }
        if ("stripe_demo".equals(paymentRequest.getProvider()) && !blank(stripeSecretKey)) {
            return createStripeCheckout(paymentRequest, null);
        }
        return new CreatedPaymentLink("mock", publicBaseUrl + "/pay/" + paymentRequest.getPublicToken(), null, null, Map.of("mode", "mock"));
    }

    private CreatedPaymentLink createStripeCheckout(PaymentRequest paymentRequest, String stripeAccountId) {
        Map<String, String> form = stripeCheckoutPayload(paymentRequest);
        Map<String, String> headers = stripeAccountId != null ? Map.of("Stripe-Account", stripeAccountId) : null;
        Map<String, Object> data = stripePost("https://api.stripe.com/v1/checkout/sessions", form, headers);
        return new CreatedPaymentLink(
            stripeAccountId != null ? "stripe_connect" : "stripe_demo",
            string(data.get("url")),
            string(data.get("payment_intent")),
            string(data.get("id")),
            stripeAccountId != null
                ? Map.of("mode", "stripe_connect_checkout", "session_id", string(data.get("id")), "livemode", bool(data.get("livemode")), "stripe_account_id", stripeAccountId)
                : Map.of("mode", "stripe_demo_checkout", "session_id", string(data.get("id")), "livemode", bool(data.get("livemode")))
        );
    }

    private Map<String, String> stripeCheckoutPayload(PaymentRequest paymentRequest) {
        Map<String, String> payload = new LinkedHashMap<>();
        payload.put("mode", "payment");
        payload.put("success_url", publicBaseUrl + "/pay/success?payment_request_id=" + paymentRequest.getId() + "&session_id={CHECKOUT_SESSION_ID}");
        payload.put("cancel_url", publicBaseUrl + "/pay/cancel?payment_request_id=" + paymentRequest.getId());
        payload.put("client_reference_id", String.valueOf(paymentRequest.getId()));
        payload.put("metadata[payment_request_id]", String.valueOf(paymentRequest.getId()));
        payload.put("metadata[sid]", paymentRequest.getSid());
        payload.put("metadata[organization_id]", String.valueOf(paymentRequest.getOrganization().getId()));
        payload.put("line_items[0][quantity]", "1");
        payload.put("line_items[0][price_data][currency]", paymentRequest.getCurrency().toLowerCase());
        payload.put("line_items[0][price_data][unit_amount]", String.valueOf(paymentRequest.getAmountCents()));
        payload.put("line_items[0][price_data][product_data][name]", paymentRequest.getPurpose());
        if (!blank(paymentRequest.getNote())) {
            payload.put("line_items[0][price_data][product_data][description]", truncate(paymentRequest.getNote(), 500));
        }
        return payload;
    }

    private Map<String, Object> stripeGet(String url, Map<String, String> extraHeaders) {
        try {
            HttpRequest.Builder builder = HttpRequest.newBuilder().uri(URI.create(url)).timeout(Duration.ofSeconds(20)).GET();
            builder.header("Authorization", "Basic " + basicAuthValue());
            if (extraHeaders != null) {
                extraHeaders.forEach(builder::header);
            }
            HttpResponse<String> response = httpClient.send(builder.build(), HttpResponse.BodyHandlers.ofString());
            if (response.statusCode() >= 400) {
                throw new IllegalStateException("Stripe returned status " + response.statusCode() + ": " + response.body());
            }
            return objectMapper.readValue(response.body(), new TypeReference<>() {});
        } catch (IOException | InterruptedException ex) {
            if (ex instanceof InterruptedException) Thread.currentThread().interrupt();
            throw new IllegalStateException("Stripe request failed", ex);
        }
    }

    private Map<String, Object> stripePost(String url, Map<String, String> form, Map<String, String> extraHeaders) {
        try {
            HttpRequest.Builder builder = HttpRequest.newBuilder()
                .uri(URI.create(url))
                .timeout(Duration.ofSeconds(20))
                .header("Authorization", "Basic " + basicAuthValue())
                .header("Content-Type", "application/x-www-form-urlencoded")
                .POST(HttpRequest.BodyPublishers.ofString(formEncode(form)));
            if (extraHeaders != null) {
                extraHeaders.forEach(builder::header);
            }
            HttpResponse<String> response = httpClient.send(builder.build(), HttpResponse.BodyHandlers.ofString());
            if (response.statusCode() >= 400) {
                throw new IllegalStateException("Stripe returned status " + response.statusCode() + ": " + response.body());
            }
            return objectMapper.readValue(response.body(), new TypeReference<>() {});
        } catch (IOException | InterruptedException ex) {
            if (ex instanceof InterruptedException) Thread.currentThread().interrupt();
            throw new IllegalStateException("Stripe request failed", ex);
        }
    }

    private int amountToCents(Double amount) {
        BigDecimal value = BigDecimal.valueOf(amount != null ? amount : 0.0d).setScale(2, RoundingMode.HALF_UP);
        int cents = value.multiply(BigDecimal.valueOf(100)).intValue();
        return Math.max(cents, 1);
    }

    private String token(int bytes) {
        byte[] raw = new byte[bytes];
        secureRandom.nextBytes(raw);
        return Base64.getUrlEncoder().withoutPadding().encodeToString(raw);
    }

    private String formEncode(Map<String, String> form) {
        StringBuilder out = new StringBuilder();
        boolean first = true;
        for (Map.Entry<String, String> entry : form.entrySet()) {
            if (!first) out.append('&');
            first = false;
            out.append(encode(entry.getKey())).append('=').append(encode(entry.getValue()));
        }
        return out.toString();
    }

    private String basicAuthValue() {
        return Base64.getEncoder().encodeToString((stripeSecretKey + ":").getBytes(StandardCharsets.UTF_8));
    }

    private String encode(String value) {
        return URLEncoder.encode(value != null ? value : "", StandardCharsets.UTF_8);
    }

    private String string(Object value) {
        return value != null ? String.valueOf(value) : null;
    }

    private boolean bool(Object value) {
        if (value instanceof Boolean b) return b;
        if (value instanceof Number n) return n.intValue() != 0;
        if (value instanceof String s) return "true".equalsIgnoreCase(s) || "1".equals(s);
        return false;
    }

    private boolean blank(String value) {
        return value == null || value.isBlank();
    }

    private String stripTrailingSlash(String value) {
        return value.endsWith("/") ? value.substring(0, value.length() - 1) : value;
    }

    private String truncate(String value, int max) {
        if (value == null) return null;
        return value.length() <= max ? value : value.substring(0, max);
    }

    public record CreatedPaymentLink(
        String provider,
        String paymentUrl,
        String providerPaymentId,
        String providerSessionId,
        Map<String, Object> providerPayload
    ) {
    }
}
