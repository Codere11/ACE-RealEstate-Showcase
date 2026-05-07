package com.ace.platform.chat;

import com.ace.platform.conversation.ConversationMessage;
import com.ace.platform.conversation.ConversationService;
import com.ace.platform.events.LeadEventService;
import com.ace.platform.lead.Lead;
import com.ace.platform.lead.LeadService;
import com.ace.platform.organization.Organization;
import com.ace.platform.organization.OrganizationRepository;
import com.ace.platform.user.User;
import com.ace.platform.user.UserRepository;
import org.springframework.http.HttpStatus;
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

import java.time.ZoneOffset;
import java.util.List;
import java.util.Map;

@RestController
public class ChatApiController {

    private final OrganizationRepository organizationRepository;
    private final UserRepository userRepository;
    private final LeadService leadService;
    private final ConversationService conversationService;
    private final PublicChatService publicChatService;
    private final TakeoverService takeoverService;
    private final LeadEventService leadEventService;

    public ChatApiController(
        OrganizationRepository organizationRepository,
        UserRepository userRepository,
        LeadService leadService,
        ConversationService conversationService,
        PublicChatService publicChatService,
        TakeoverService takeoverService,
        LeadEventService leadEventService
    ) {
        this.organizationRepository = organizationRepository;
        this.userRepository = userRepository;
        this.leadService = leadService;
        this.conversationService = conversationService;
        this.publicChatService = publicChatService;
        this.takeoverService = takeoverService;
        this.leadEventService = leadEventService;
    }

    @PostMapping({"/chat", "/chat/"})
    public ChatResponse chat(@RequestBody ChatRequest request) {
        Organization organization = resolveOrganization(request.tenant_slug(), request.meta());
        PublicChatService.ChatResult result = publicChatService.handleVisitorMessage(
            organization,
            request.sid(),
            request.meta() != null ? request.meta().getOrDefault("survey_slug", "start") : "start",
            request.message()
        );
        return new ChatResponse(result.sid(), result.reply(), result.chatMode(), result.storyComplete(), result.surveyProgress(), result.suggestedChoices());
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

    private Organization resolveOrganization(String tenantSlug, Map<String, String> meta) {
        String effectiveSlug = tenantSlug;
        if ((effectiveSlug == null || effectiveSlug.isBlank()) && meta != null) {
            effectiveSlug = meta.get("organization_slug");
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
        if (user.getOrganization() == null) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Organization context is required");
        }
        return user.getOrganization().getId();
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

    public record ChatRequest(String sid, String message, String tenant_slug, Map<String, String> meta) {
    }

    public record ChatResponse(String sid, String reply, String chatMode, boolean storyComplete, int surveyProgress, List<String> quickReplies) {
    }

    public record StaffMessageRequest(Long orgId, String sid, String text) {
    }

    public record LeadSummary(String sid, String name, String status, int surveyProgress, String lastMessage, boolean takeoverActive) {
        static LeadSummary from(Lead lead) {
            return new LeadSummary(
                lead.getSid(),
                lead.getDisplayName(),
                lead.getStatus().name(),
                lead.getSurveyProgress(),
                lead.getLastMessagePreview(),
                lead.isTakeoverActive()
            );
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
}
