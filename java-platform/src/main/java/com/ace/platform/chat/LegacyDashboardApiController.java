package com.ace.platform.chat;

import com.ace.platform.conversation.ConversationMessage;
import com.ace.platform.conversation.ConversationRole;
import com.ace.platform.conversation.ConversationService;
import com.ace.platform.events.LeadEventService;
import com.ace.platform.lead.Lead;
import com.ace.platform.lead.LeadService;
import com.ace.platform.organization.Organization;
import com.ace.platform.organization.OrganizationRepository;
import com.ace.platform.payment.OrganizationPaymentSettings;
import com.ace.platform.payment.PaymentRequest;
import com.ace.platform.payment.PaymentService;
import com.ace.platform.user.User;
import com.ace.platform.user.UserRepository;
import com.ace.platform.user.UserRole;
import com.fasterxml.jackson.annotation.JsonProperty;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;
import org.springframework.security.core.Authentication;

import java.time.Instant;
import java.time.ZoneOffset;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@RestController
public class LegacyDashboardApiController {

    private final UserRepository userRepository;
    private final OrganizationRepository organizationRepository;
    private final LeadService leadService;
    private final ConversationService conversationService;
    private final LeadEventService leadEventService;
    private final PaymentService paymentService;

    public LegacyDashboardApiController(
        UserRepository userRepository,
        OrganizationRepository organizationRepository,
        LeadService leadService,
        ConversationService conversationService,
        LeadEventService leadEventService,
        org.springframework.beans.factory.ObjectProvider<PaymentService> paymentServiceProvider
    ) {
        this.userRepository = userRepository;
        this.organizationRepository = organizationRepository;
        this.leadService = leadService;
        this.conversationService = conversationService;
        this.leadEventService = leadEventService;
        this.paymentService = paymentServiceProvider.getIfAvailable();
    }

    @GetMapping("/leads/")
    public List<LeadRow> leads(Authentication authentication) {
        Organization organization = resolveOrganization(authentication);
        return leadService.listForOrganization(organization.getId()).stream().map(this::toLeadRow).toList();
    }

    @DeleteMapping("/leads/{sid}")
    public Map<String, Object> deleteLead(@PathVariable String sid, Authentication authentication) {
        Organization organization = resolveOrganization(authentication);
        Lead lead = leadService.findByOrganizationAndSid(organization.getId(), sid)
            .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Lead not found"));
        leadService.deleteLead(lead);
        return Map.of("success", true, "message", "Lead deleted");
    }

    @GetMapping({"/chats", "/chats/"})
    public List<ChatLog> chats(@RequestParam(required = false) String sid, Authentication authentication) {
        Organization organization = resolveOrganization(authentication);
        if (sid != null && !sid.isBlank()) {
            Lead lead = leadService.findByOrganizationAndSid(organization.getId(), sid)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Lead not found"));
            return conversationService.getThread(lead).stream().map(this::toChatLog).toList();
        }
        List<ChatLog> out = new ArrayList<>();
        for (Lead lead : leadService.listForOrganization(organization.getId())) {
            out.addAll(conversationService.getThread(lead).stream().map(this::toChatLog).toList());
        }
        out.sort(Comparator.comparingLong(ChatLog::timestamp));
        return out;
    }

    @GetMapping("/kpis/")
    public Map<String, Object> kpis(Authentication authentication) {
        Organization organization = resolveOrganization(authentication);
        List<Lead> leads = leadService.listForOrganization(organization.getId());
        long contacts = leads.stream().filter(lead -> hasText(lead.getEmail()) || hasText(lead.getPhone())).count();
        return Map.of(
            "visitors", leads.size(),
            "interactions", leads.size(),
            "contacts", contacts,
            "avgResponseSec", 0,
            "activeLeads", leads.size()
        );
    }

    @GetMapping("/funnel/")
    public Map<String, Object> funnel(Authentication authentication) {
        Organization organization = resolveOrganization(authentication);
        List<Lead> leads = leadService.listForOrganization(organization.getId());
        long awareness = leads.size();
        long interest = leads.stream().filter(lead -> lead.getSurveyProgress() > 0 || lead.getQualificationScore() != null).count();
        long meeting = leads.stream().filter(lead -> lead.isTakeoverEligible() || lead.isVideoOfferEligible()).count();
        long close = leads.stream().filter(lead -> lead.getQualificationScore() != null && lead.getQualificationScore() >= 85).count();
        return Map.of(
            "awareness", awareness,
            "interest", interest,
            "meeting", meeting,
            "close", close
        );
    }

    @GetMapping("/objections/")
    public List<String> objections() {
        return List.of();
    }

    @GetMapping("/api/organizations/{orgId}/qualifiers/lead-profiles")
    public List<LeadProfileResponse> leadProfiles(@PathVariable Long orgId, Authentication authentication) {
        User user = requireUser(authentication);
        requireOrgAccess(user, orgId);
        return leadService.listForOrganization(orgId).stream().map(this::toLeadProfile).toList();
    }

    @GetMapping("/api/organizations/{orgId}/payment-settings")
    public Map<String, Object> paymentSettings(@PathVariable Long orgId, Authentication authentication) {
        User user = requireUser(authentication);
        requireOrgAccess(user, orgId);
        PaymentService payments = requirePaymentService();
        OrganizationPaymentSettings settings = payments.getOrCreateSettings(orgId);
        return payments.toSettingsPayload(settings);
    }

    @PostMapping("/api/organizations/{orgId}/payment-settings/stripe/connect")
    public Map<String, Object> startStripeConnect(@PathVariable Long orgId, Authentication authentication) {
        User user = requireUser(authentication);
        requireOrgAccess(user, orgId);
        try {
            return Map.of("url", requirePaymentService().createConnectLink(orgId));
        } catch (IllegalStateException ex) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, ex.getMessage());
        }
    }

    @PostMapping("/api/organizations/{orgId}/payment-settings/stripe/refresh")
    public Map<String, Object> refreshStripeConnect(@PathVariable Long orgId, Authentication authentication) {
        User user = requireUser(authentication);
        requireOrgAccess(user, orgId);
        try {
            PaymentService payments = requirePaymentService();
            OrganizationPaymentSettings settings = payments.refreshConnectStatus(payments.getOrCreateSettings(orgId));
            return payments.toSettingsPayload(settings);
        } catch (IllegalStateException ex) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, ex.getMessage());
        }
    }

    @GetMapping("/api/organizations/{orgId}/payment-requests")
    public List<Map<String, Object>> paymentRequests(@PathVariable Long orgId, @RequestParam(required = false) String sid, Authentication authentication) {
        User user = requireUser(authentication);
        requireOrgAccess(user, orgId);
        PaymentService payments = requirePaymentService();
        return payments.listRequests(orgId, sid, 100).stream().map(payments::toPaymentRequestPayload).toList();
    }

    @PostMapping("/api/organizations/{orgId}/payment-requests")
    public Map<String, Object> createPaymentRequest(@PathVariable Long orgId, @RequestBody PaymentRequestCreate request, Authentication authentication) {
        User user = requireUser(authentication);
        requireOrgAccess(user, orgId);
        Lead lead = leadService.findByOrganizationAndSid(orgId, request.sid())
            .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Lead not found"));
        PaymentRequest item;
        try {
            item = requirePaymentService().createPaymentRequest(
                orgId,
                request.sid(),
                user,
                request.amount(),
                request.currency(),
                request.purpose(),
                request.note(),
                request.expiresInHours()
            );
        } catch (IllegalStateException ex) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, ex.getMessage());
        }

        Map<String, Object> eventPayload = new LinkedHashMap<>();
        eventPayload.put("id", item.getId());
        eventPayload.put("status", item.getStatus());
        eventPayload.put("amountCents", item.getAmountCents());
        eventPayload.put("currency", item.getCurrency());
        eventPayload.put("purpose", item.getPurpose());
        eventPayload.put("note", item.getNote());
        eventPayload.put("paymentUrl", item.getPaymentUrl());
        eventPayload.put("expiresAt", item.getExpiresAt() != null ? item.getExpiresAt().toString() : null);
        eventPayload.put("paidAt", item.getPaidAt() != null ? item.getPaidAt().toString() : null);
        leadEventService.publish(lead.getOrganization(), lead.getSid(), "payment.request.sent", eventPayload);
        conversationService.appendMessage(lead, ConversationRole.ASSISTANT, "Prejeli ste zahtevek za plačilo: " + item.getPurpose() + ". Povezava: " + item.getPaymentUrl());
        return requirePaymentService().toPaymentRequestPayload(item);
    }

    private LeadRow toLeadRow(Lead lead) {
        int score = lead.getQualificationScore() != null ? lead.getQualificationScore() : lead.getSurveyProgress();
        return new LeadRow(
            lead.getSid(),
            lead.getDisplayName(),
            "",
            score,
            lead.getStatus().name().toLowerCase(),
            lead.isTakeoverEligible() || lead.isVideoOfferEligible(),
            interest(score),
            lead.getPhone(),
            lead.getEmail(),
            hasText(lead.getPhone()),
            hasText(lead.getEmail()),
            false,
            lead.getLastMessagePreview() != null ? lead.getLastMessagePreview() : "",
            lead.getLastMessageAt() != null ? Math.max(0, Instant.now().getEpochSecond() - lead.getLastMessageAt().getEpochSecond()) : Integer.MAX_VALUE,
            lead.getQualificationReasoning() != null ? lead.getQualificationReasoning() : "",
            null,
            null,
            null,
            null
        );
    }

    private LeadProfileResponse toLeadProfile(Lead lead) {
        return new LeadProfileResponse(
            lead.getId(),
            lead.getOrganization().getId(),
            lead.getSid(),
            null,
            1,
            lead.getQualifierProfile(),
            Map.of(),
            lead.getQualificationScore() != null ? lead.getQualificationScore() : lead.getSurveyProgress(),
            lead.getQualificationBand() != null ? lead.getQualificationBand() : band(lead.getQualificationScore() != null ? lead.getQualificationScore() : lead.getSurveyProgress()),
            lead.getConfidenceOverall() != null ? lead.getConfidenceOverall() : 0.0,
            lead.getQualificationReasoning() != null ? lead.getQualificationReasoning() : "",
            lead.isTakeoverEligible() ? "Human takeover recommended" : "Continue qualification",
            lead.getQualifierMissingFields(),
            lead.isTakeoverEligible(),
            lead.isVideoOfferEligible(),
            null,
            lead.getCreatedAt(),
            lead.getUpdatedAt()
        );
    }

    private ChatLog toChatLog(ConversationMessage message) {
        return new ChatLog(
            message.getLead().getSid(),
            message.getRole().apiValue(),
            message.getText(),
            message.getCreatedAt().atOffset(ZoneOffset.UTC).toInstant().toEpochMilli()
        );
    }

    private Organization resolveOrganization(Authentication authentication) {
        User user = requireUser(authentication);
        if (user.getOrganization() != null) {
            return user.getOrganization();
        }
        if (user.getRole() == UserRole.PLATFORM_ADMIN) {
            return organizationRepository.findAll().stream()
                .filter(Organization::isActive)
                .findFirst()
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.BAD_REQUEST, "Organization context is required"));
        }
        throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Organization context is required");
    }

    private User requireUser(Authentication authentication) {
        if (authentication == null || authentication.getName() == null) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Authentication required");
        }
        return userRepository.findByUsername(authentication.getName())
            .orElseThrow(() -> new ResponseStatusException(HttpStatus.UNAUTHORIZED, "User not found"));
    }

    private void requireOrgAccess(User user, Long orgId) {
        boolean platformAdmin = user.getRole() == UserRole.PLATFORM_ADMIN;
        boolean sameOrg = user.getOrganization() != null && orgId.equals(user.getOrganization().getId());
        if (!platformAdmin && !sameOrg) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "This user cannot access the requested organization");
        }
    }

    private PaymentService requirePaymentService() {
        if (paymentService == null) {
            throw new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE, "Payments are not available");
        }
        return paymentService;
    }

    private boolean hasText(String value) {
        return value != null && !value.isBlank();
    }

    private String interest(int score) {
        if (score >= 70) return "High";
        if (score >= 40) return "Medium";
        return "Low";
    }

    private String band(int score) {
        if (score >= 70) return "hot";
        if (score >= 40) return "warm";
        return "cold";
    }

    public record LeadRow(
        String id,
        String name,
        String industry,
        int score,
        String stage,
        boolean compatibility,
        String interest,
        String phoneText,
        String emailText,
        boolean phone,
        boolean email,
        boolean adsExp,
        String lastMessage,
        long lastSeenSec,
        String notes,
        String survey_started_at,
        String survey_completed_at,
        Map<String, Object> survey_answers,
        Integer survey_progress
    ) {
    }

    public record ChatLog(String sid, String role, String text, long timestamp) {
    }

    public record LeadProfileResponse(
        Long id,
        @JsonProperty("organization_id") Long organizationId,
        String sid,
        @JsonProperty("qualifier_id") Long qualifierId,
        @JsonProperty("qualifier_version") int qualifierVersion,
        Map<String, Object> profile,
        @JsonProperty("field_confidence") Map<String, Double> fieldConfidence,
        @JsonProperty("qualification_score") int qualificationScore,
        @JsonProperty("qualification_band") String qualificationBand,
        @JsonProperty("confidence_overall") double confidenceOverall,
        String reasoning,
        @JsonProperty("recommended_next_action") String recommendedNextAction,
        @JsonProperty("missing_fields") List<String> missingFields,
        @JsonProperty("takeover_eligible") boolean takeoverEligible,
        @JsonProperty("video_offer_eligible") boolean videoOfferEligible,
        @JsonProperty("last_qualified_at") Instant lastQualifiedAt,
        @JsonProperty("created_at") Instant createdAt,
        @JsonProperty("updated_at") Instant updatedAt
    ) {
    }

    public record PaymentRequestCreate(String sid, Double amount, String currency, String purpose, String note, @JsonProperty("expires_in_hours") Integer expiresInHours) {
    }
}
