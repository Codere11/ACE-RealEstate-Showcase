package com.ace.platform.chat;

import com.ace.platform.conversation.ConversationMessage;
import com.ace.platform.conversation.ConversationService;
import com.ace.platform.events.LeadEventService;
import com.ace.platform.lead.Lead;
import com.ace.platform.lead.LeadService;
import com.ace.platform.organization.Organization;
import com.ace.platform.organization.OrganizationRepository;
import com.ace.platform.qualifier.QualifierChatService;
import com.ace.platform.qualifier.QualifierService;
import com.ace.platform.user.User;
import com.ace.platform.user.UserRepository;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;
import org.springframework.web.servlet.mvc.method.annotation.StreamingResponseBody;

import java.nio.charset.StandardCharsets;
import java.time.ZoneOffset;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

@RestController
public class ChatApiController {

    private static final Pattern STREAM_TOKEN_PATTERN = Pattern.compile("\\S+\\s*|\\s+");

    private final OrganizationRepository organizationRepository;
    private final UserRepository userRepository;
    private final LeadService leadService;
    private final ConversationService conversationService;
    private final PublicChatService publicChatService;
    private final QualifierService qualifierService;
    private final QualifierChatService qualifierChatService;
    private final TakeoverService takeoverService;
    private final LeadEventService leadEventService;

    public ChatApiController(
        OrganizationRepository organizationRepository,
        UserRepository userRepository,
        LeadService leadService,
        ConversationService conversationService,
        PublicChatService publicChatService,
        QualifierService qualifierService,
        QualifierChatService qualifierChatService,
        TakeoverService takeoverService,
        LeadEventService leadEventService
    ) {
        this.organizationRepository = organizationRepository;
        this.userRepository = userRepository;
        this.leadService = leadService;
        this.conversationService = conversationService;
        this.publicChatService = publicChatService;
        this.qualifierService = qualifierService;
        this.qualifierChatService = qualifierChatService;
        this.takeoverService = takeoverService;
        this.leadEventService = leadEventService;
    }

    @PostMapping({"/chat", "/chat/", "/api/public/chat"})
    public ChatResponse chat(@RequestBody ChatRequest request) {
        return handleChat(request);
    }

    @PostMapping(value = {"/chat/stream", "/chat/stream/", "/api/public/chat/stream"}, produces = MediaType.TEXT_PLAIN_VALUE)
    public ResponseEntity<StreamingResponseBody> chatStream(@RequestBody ChatRequest request) {
        StreamingResponseBody stream = outputStream -> {
            ChatResponse response = handleChat(request);
            String reply = response.reply() != null ? response.reply() : "";
            if (reply.isBlank()) {
                outputStream.flush();
                return;
            }
            for (String chunk : streamChunks(reply)) {
                outputStream.write(chunk.getBytes(StandardCharsets.UTF_8));
                outputStream.flush();
                try {
                    Thread.sleep(chunk.strip().length() <= 2 ? 12L : 20L);
                } catch (InterruptedException ex) {
                    Thread.currentThread().interrupt();
                    break;
                }
            }
        };
        return ResponseEntity.ok()
            .contentType(MediaType.TEXT_PLAIN)
            .header(HttpHeaders.CACHE_CONTROL, "no-store, no-transform")
            .header("X-Accel-Buffering", "no")
            .header("X-ACE-Sid", request.sid() != null ? request.sid() : "")
            .body(stream);
    }

    @PostMapping({"/chat/staff", "/chat/staff/"})
    public Map<String, Object> staff(@RequestBody StaffMessageRequest request, Authentication authentication) {
        User user = requireUser(authentication);
        Long orgId = resolveStaffOrganizationId(user, request.orgId());
        Lead lead = leadService.findByOrganizationAndSid(orgId, request.sid())
            .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Lead not found"));
        takeoverService.startTakeover(lead, user, request.text());
        return Map.of("ok", true, "sid", lead.getSid(), "takeover", takeoverService.takeoverSummary(lead));
    }

    @GetMapping("/chat-events/poll")
    public Map<String, Object> poll(
        @RequestParam String sid,
        @RequestParam(defaultValue = "0") long since,
        @RequestParam(defaultValue = "20") double timeout,
        @RequestParam(defaultValue = "200") int limit,
        @RequestParam(required = false) String tenantSlug,
        Authentication authentication
    ) {
        Long organizationId = resolveOrganizationId(sid, tenantSlug, authentication);
        List<Map<String, Object>> events = leadEventService.poll(organizationId, sid, since, timeout, limit);
        long next = events.stream()
            .map(e -> e.get("_seq"))
            .filter(Long.class::isInstance)
            .map(Long.class::cast)
            .max(Long::compareTo)
            .orElse(since);
        return Map.of("ok", true, "events", events, "next", next);
    }

    @GetMapping("/api/organizations/{orgId}/leads")
    public List<LeadSummary> leads(@PathVariable Long orgId, Authentication authentication) {
        User user = requireUser(authentication);
        requireOrgAccess(user, orgId);
        return leadService.listForOrganization(orgId).stream().map(LeadSummary::from).toList();
    }

    @GetMapping("/api/organizations/{orgId}/leads/{sid}/messages")
    public List<MessageResponse> thread(@PathVariable Long orgId, @PathVariable String sid, Authentication authentication) {
        User user = requireUser(authentication);
        requireOrgAccess(user, orgId);
        Lead lead = leadService.findByOrganizationAndSid(orgId, sid)
            .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Lead not found"));
        return conversationService.getThread(lead).stream().map(MessageResponse::from).toList();
    }

    @GetMapping("/api/public/organizations/{orgSlug}/leads/{sid}/messages")
    public List<MessageResponse> publicThread(@PathVariable String orgSlug, @PathVariable String sid) {
        Organization organization = organizationRepository.findBySlugAndActiveTrue(orgSlug)
            .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Organization not found"));
        Lead lead = leadService.findByOrganizationAndSid(organization.getId(), sid)
            .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Lead not found"));
        return conversationService.getThread(lead).stream().map(MessageResponse::from).toList();
    }

    @PostMapping("/api/public/organizations/{orgSlug}/leads/{sid}/request-staff")
    public Map<String, Object> requestStaff(@PathVariable String orgSlug, @PathVariable String sid) {
        Organization org = organizationRepository.findBySlugAndActiveTrue(orgSlug)
            .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Organization not found"));
        Lead lead = leadService.findByOrganizationAndSid(org.getId(), sid)
            .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Lead not found"));
        lead.setStaffRequested(true);
        leadService.touchLead(lead, "Visitor requested staff");
        leadEventService.publish(org, sid, "lead.staff-requested", Map.of("sid", sid, "staff_requested", true));
        return Map.of("ok", true, "sid", sid);
    }

    @PostMapping("/api/organizations/{orgId}/leads/{sid}/takeover/end")
    public Map<String, Object> endTakeover(@PathVariable Long orgId, @PathVariable String sid, Authentication authentication) {
        User user = requireUser(authentication);
        requireOrgAccess(user, orgId);
        Lead lead = leadService.findByOrganizationAndSid(orgId, sid)
            .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Lead not found"));
        takeoverService.endTakeover(lead);
        return Map.of("ok", true, "sid", sid, "takeover", takeoverService.takeoverSummary(lead));
    }

    @DeleteMapping("/api/organizations/{orgId}/leads/{sid}")
    public Map<String, Object> deleteLead(@PathVariable Long orgId, @PathVariable String sid, Authentication authentication) {
        User user = requireUser(authentication);
        requireOrgAccess(user, orgId);
        Lead lead = leadService.findByOrganizationAndSid(orgId, sid)
            .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Lead not found"));
        leadEventService.publish(lead.getOrganization(), lead.getSid(), "lead.deleted", Map.of(
            "sid", lead.getSid(),
            "deleted", true
        ));
        leadService.deleteLead(lead);
        return Map.of("ok", true, "sid", sid);
    }

    private List<String> streamChunks(String text) {
        Matcher matcher = STREAM_TOKEN_PATTERN.matcher(text != null ? text : "");
        java.util.ArrayList<String> chunks = new java.util.ArrayList<>();
        while (matcher.find()) {
            String token = matcher.group();
            if (token == null || token.isEmpty()) {
                continue;
            }
            if (token.length() <= 18) {
                chunks.add(token);
                continue;
            }
            for (int i = 0; i < token.length(); i += 12) {
                chunks.add(token.substring(i, Math.min(token.length(), i + 12)));
            }
        }
        if (chunks.isEmpty() && text != null && !text.isEmpty()) {
            chunks.add(text);
        }
        return chunks;
    }

    private ChatResponse handleChat(ChatRequest request) {
        Organization organization = resolveOrganization(request.tenant_slug(), request.meta());
        boolean explicitSurveyMode = request.meta() != null
            && request.meta().get("survey_slug") != null
            && !String.valueOf(request.meta().get("survey_slug")).isBlank();
        ChatResponse response;
        if (!explicitSurveyMode && qualifierService.findActive(organization.getId()).isPresent()) {
            Map<String, Object> spatial = request.meta() != null ? toMap(request.meta().get("spatialContext")) : null;
            QualifierChatService.QualifierChatResult result = qualifierChatService.handleVisitorMessage(
                organization,
                request.sid(),
                request.message(),
                spatial
            );
            response = new ChatResponse(
                result.sid(),
                result.reply(),
                "open",
                false,
                100,
                null,
                null,
                null
            );
        } else {
            PublicChatService.ChatResult result = publicChatService.handleVisitorMessage(
                organization,
                request.sid(),
                request.meta() != null ? String.valueOf(request.meta().getOrDefault("survey_slug", "start")) : "start",
                request.message()
            );
            response = new ChatResponse(
                result.sid(),
                result.reply(),
                result.chatMode(),
                result.storyComplete(),
                result.surveyProgress(),
                result.currentStep() != null ? SurveyStepResponse.from(result.currentStep()) : null,
                result.completionTitle(),
                result.completionSubtitle()
            );
        }
        publishLeadRealtimeState(organization, response.sid());
        return response;
    }

    private void publishLeadRealtimeState(Organization organization, String sid) {
        if (organization == null || sid == null || sid.isBlank()) {
            return;
        }
        leadService.findByOrganizationAndSid(organization.getId(), sid).ifPresent(lead -> {
            Map<String, Object> touched = new LinkedHashMap<>();
            touched.put("lastMessage", lead.getLastMessagePreview());
            touched.put("lastSeenSec", lead.getLastMessageAt() != null ? lead.getLastMessageAt().getEpochSecond() : null);
            touched.put("survey_progress", lead.getSurveyProgress());
            touched.put("takeover_active", lead.isTakeoverActive());
            touched.put("status", lead.getStatus().name());
            touched.put("qualification_score", lead.getQualificationScore());
            touched.put("qualification_band", lead.getQualificationBand());
            touched.put("confidence_overall", lead.getConfidenceOverall());
            touched.put("takeover_eligible", lead.isTakeoverEligible());
            touched.put("video_offer_eligible", lead.isVideoOfferEligible());
            leadEventService.publish(lead.getOrganization(), lead.getSid(), "lead.touched", touched);

            if (lead.getQualifierProfile() != null && !lead.getQualifierProfile().isEmpty()) {
                leadEventService.publish(lead.getOrganization(), lead.getSid(), "lead.profile.updated", Map.of(
                    "profile", lead.getQualifierProfile(),
                    "missing_fields", lead.getQualifierMissingFields() != null ? lead.getQualifierMissingFields() : List.of(),
                    "confidence_overall", lead.getConfidenceOverall() != null ? lead.getConfidenceOverall() : 0.0
                ));
                leadEventService.publish(lead.getOrganization(), lead.getSid(), "lead.qualified", Map.of(
                    "qualification_score", lead.getQualificationScore() != null ? lead.getQualificationScore() : 0,
                    "qualification_band", lead.getQualificationBand() != null ? lead.getQualificationBand() : "cold",
                    "reasoning", lead.getQualificationReasoning() != null ? lead.getQualificationReasoning() : "",
                    "takeover_eligible", lead.isTakeoverEligible(),
                    "video_offer_eligible", lead.isVideoOfferEligible(),
                    "confidence_overall", lead.getConfidenceOverall() != null ? lead.getConfidenceOverall() : 0.0
                ));
            }
        });
    }

    private Organization resolveOrganization(String tenantSlug, Map<String, Object> meta) {
        String effectiveSlug = tenantSlug;
        if ((effectiveSlug == null || effectiveSlug.isBlank()) && meta != null) {
            Object slugObj = meta.get("organization_slug");
            if (slugObj != null) effectiveSlug = String.valueOf(slugObj);
        }
        if (effectiveSlug == null || effectiveSlug.isBlank()) {
            effectiveSlug = "demo";
        }
        return organizationRepository.findBySlugAndActiveTrue(effectiveSlug)
            .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Organization not found"));
    }

    private Long resolveOrganizationId(String sid, String tenantSlug, Authentication authentication) {
        if (tenantSlug != null && !tenantSlug.isBlank()) {
            return organizationRepository.findBySlugAndActiveTrue(tenantSlug)
                .map(Organization::getId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Organization not found"));
        }
        User user = requireUser(authentication);
        if (user.getOrganization() != null) {
            return user.getOrganization().getId();
        }
        if (user.getRole().name().equals("PLATFORM_ADMIN")) {
            return organizationRepository.findAll().stream()
                .filter(Organization::isActive)
                .findFirst()
                .map(Organization::getId)
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
        boolean platformAdmin = user.getRole().name().equals("PLATFORM_ADMIN");
        boolean sameOrg = user.getOrganization() != null && orgId.equals(user.getOrganization().getId());
        if (!platformAdmin && !sameOrg) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "This user cannot access the requested organization");
        }
    }

    private Long resolveStaffOrganizationId(User user, Long requestedOrgId) {
        if (requestedOrgId != null) {
            requireOrgAccess(user, requestedOrgId);
            return requestedOrgId;
        }
        if (user.getOrganization() == null) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Organization context is required for staff takeover messages");
        }
        return user.getOrganization().getId();
    }

    public record ChatRequest(String sid, String message, String tenant_slug, Map<String, Object> meta) {
    }

    public record ChatResponse(
        String sid,
        String reply,
        String chatMode,
        boolean storyComplete,
        int surveyProgress,
        SurveyStepResponse currentStep,
        String completionTitle,
        String completionSubtitle
    ) {
    }

    public record SurveyStepResponse(
        int orderIndex,
        String questionType,
        String title,
        String description,
        String placeholder,
        List<String> options
    ) {
        static SurveyStepResponse from(PublicChatService.SurveyStep step) {
            return new SurveyStepResponse(step.orderIndex(), step.questionType(), step.title(), step.description(), step.placeholder(), step.options());
        }
    }

    public record StaffMessageRequest(Long orgId, String sid, String text) {
    }

    public record LeadSummary(
        String id,
        String sid,
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
        Integer surveyProgress,
        boolean takeoverActive,
        String status,
        boolean staffRequested
    ) {
        static LeadSummary from(Lead lead) {
            int score = lead.getQualificationScore() != null ? lead.getQualificationScore() : lead.getSurveyProgress();
            return new LeadSummary(
                lead.getSid(),
                lead.getSid(),
                lead.getDisplayName(),
                industryFrom(lead),
                score,
                stageFrom(lead.getStatus()),
                lead.isTakeoverEligible() || lead.isVideoOfferEligible(),
                interestFrom(score, lead.getQualificationBand()),
                lead.getPhone(),
                lead.getEmail(),
                hasText(lead.getPhone()),
                hasText(lead.getEmail()),
                false,
                lead.getLastMessagePreview(),
                lead.getLastMessageAt() != null ? lead.getLastMessageAt().getEpochSecond() : (lead.getCreatedAt() != null ? lead.getCreatedAt().getEpochSecond() : 0),
                lead.getQualificationReasoning(),
                lead.getSurveyProgress(),
                lead.isTakeoverActive(),
                lead.getStatus().name(),
                lead.isStaffRequested()
            );
        }

        private static String industryFrom(Lead lead) {
            Map<String, Object> profile = lead.getQualifierProfile() != null ? lead.getQualifierProfile() : Map.of();
            String industry = text(profile.get("industry"));
            if (!industry.isBlank()) return industry;
            String businessType = text(profile.get("business_type"));
            if (!businessType.isBlank()) return businessType;
            return "Unknown";
        }

        private static String stageFrom(com.ace.platform.lead.LeadStatus status) {
            if (status == null) return "Awareness";
            return switch (status) {
                case SURVEY -> "Survey";
                case OPEN_CHAT -> "Open chat";
                case HUMAN_TAKEOVER -> "Human takeover";
                case CLOSED -> "Closed";
            };
        }

        private static String interestFrom(int score, String qualificationBand) {
            String band = qualificationBand != null ? qualificationBand.trim().toLowerCase() : "";
            if ("hot".equals(band)) return "High";
            if ("warm".equals(band)) return "Medium";
            if ("cold".equals(band)) return "Low";
            if (score >= 70) return "High";
            if (score >= 40) return "Medium";
            return "Low";
        }

        private static String text(Object value) {
            return value == null ? "" : String.valueOf(value).trim();
        }

        private static boolean hasText(String value) {
            return value != null && !value.isBlank();
        }
    }

    public record MessageResponse(String role, String text, long timestamp) {
        static MessageResponse from(ConversationMessage message) {
            return new MessageResponse(
                message.getRole().apiValue(),
                message.getText(),
                message.getCreatedAt().atOffset(ZoneOffset.UTC).toInstant().toEpochMilli()
            );
        }
    }

    @SuppressWarnings("unchecked")
    private static Map<String, Object> toMap(Object obj) {
        if (obj instanceof Map) return (Map<String, Object>) obj;
        return null;
    }
}
