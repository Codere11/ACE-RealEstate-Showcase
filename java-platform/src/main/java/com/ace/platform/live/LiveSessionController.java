package com.ace.platform.live;

import com.ace.platform.conversation.ConversationRole;
import com.ace.platform.conversation.ConversationService;
import com.ace.platform.events.LeadEventService;
import com.ace.platform.lead.Lead;
import com.ace.platform.lead.LeadService;
import com.ace.platform.organization.Organization;
import com.ace.platform.organization.OrganizationRepository;
import com.ace.platform.user.User;
import com.ace.platform.user.UserRepository;
import com.fasterxml.jackson.annotation.JsonProperty;
import org.springframework.context.annotation.Profile;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

import jakarta.servlet.http.HttpServletRequest;
import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.Map;

@RestController
@Profile("!test")
public class LiveSessionController {

    private final LiveSessionService liveSessionService;
    private final LiveKitTokenService liveKitTokenService;
    private final OrganizationRepository organizationRepository;
    private final UserRepository userRepository;
    private final LeadService leadService;
    private final LeadEventService leadEventService;
    private final ConversationService conversationService;

    public LiveSessionController(
        LiveSessionService liveSessionService,
        LiveKitTokenService liveKitTokenService,
        OrganizationRepository organizationRepository,
        UserRepository userRepository,
        LeadService leadService,
        LeadEventService leadEventService,
        ConversationService conversationService
    ) {
        this.liveSessionService = liveSessionService;
        this.liveKitTokenService = liveKitTokenService;
        this.organizationRepository = organizationRepository;
        this.userRepository = userRepository;
        this.leadService = leadService;
        this.leadEventService = leadEventService;
        this.conversationService = conversationService;
    }

    @GetMapping("/api/public/organizations/{orgSlug}/live-session")
    public PublicLiveSessionResponse publicState(@PathVariable String orgSlug, @RequestParam String sid, HttpServletRequest request) {
        Organization organization = organizationRepository.findBySlugAndActiveTrue(orgSlug)
            .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Organization not found"));
        Map<String, Object> state = liveSessionService.publicState(organization.getId(), sid);
        String status = String.valueOf(state.getOrDefault("status", "idle"));
        String roomName = (String) state.get("room_name");
        String wsUrl = null;
        String token = null;
        if ("live".equals(status) && roomName != null && !roomName.isBlank()) {
            wsUrl = resolvedWsUrl(request);
            token = liveKitTokenService.visitorToken(roomName, "visitor-sid-" + sid, "Visitor");
        }
        return new PublicLiveSessionResponse(
            sid,
            status,
            (String) state.getOrDefault("manager_display_name", ""),
            roomName,
            (String) state.getOrDefault("stage_message", ""),
            toInstant(state.get("live_at")),
            toInstant(state.get("ended_at")),
            wsUrl,
            token
        );
    }

    @GetMapping("/api/organizations/{orgId}/live-sessions/current")
    public ResponseEntity<LiveSessionResponse> current(@PathVariable Long orgId, @RequestParam String sid, Authentication authentication, HttpServletRequest request) {
        User user = requireUser(authentication);
        requireOrgAccess(user, orgId);
        return liveSessionService.getCurrent(orgId, sid)
            .map(session -> ResponseEntity.ok(toResponse(session, request, managerToken(session, user))))
            .orElseGet(() -> ResponseEntity.notFound().build());
    }

    @PostMapping("/api/organizations/{orgId}/live-sessions/preview")
    public LiveSessionResponse preview(@PathVariable Long orgId, @RequestBody LiveSessionActionRequest request, Authentication authentication, HttpServletRequest httpRequest) {
        User user = requireUser(authentication);
        requireOrgAccess(user, orgId);
        Lead lead = requireLead(orgId, request.sid());
        LiveSession session = liveSessionService.upsertPreview(lead.getOrganization(), lead.getSid(), user, user.getUsername());
        return toResponse(session, httpRequest, managerToken(session, user));
    }

    @PostMapping("/api/organizations/{orgId}/live-sessions/go-live")
    public LiveSessionResponse goLive(@PathVariable Long orgId, @RequestBody LiveSessionActionRequest request, Authentication authentication, HttpServletRequest httpRequest) {
        User user = requireUser(authentication);
        requireOrgAccess(user, orgId);
        Lead lead = requireLead(orgId, request.sid());
        LiveSession session = liveSessionService.goLive(lead.getOrganization(), lead.getSid(), user, user.getUsername());
        publishLiveEvent(lead, session);
        conversationService.appendMessage(lead, ConversationRole.ASSISTANT, user.getUsername() + " is joining to help live.");
        return toResponse(session, httpRequest, managerToken(session, user));
    }

    @PostMapping("/api/organizations/{orgId}/live-sessions/{sessionId}/end")
    public LiveSessionResponse end(@PathVariable Long orgId, @PathVariable Long sessionId, @RequestBody(required = false) LiveSessionActionRequest request, Authentication authentication, HttpServletRequest httpRequest) {
        User user = requireUser(authentication);
        requireOrgAccess(user, orgId);
        LiveSession session = liveSessionService.end(orgId, sessionId)
            .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Live session not found"));
        String effectiveSid = request != null && request.sid() != null && !request.sid().isBlank() ? request.sid() : session.getSid();
        Lead lead = requireLead(orgId, effectiveSid);
        publishEndedEvent(lead, session);
        conversationService.appendMessage(lead, ConversationRole.ASSISTANT, "Live help has ended.");
        return toResponse(session, httpRequest, null);
    }

    private LiveSessionResponse toResponse(LiveSession session, HttpServletRequest request, String token) {
        return new LiveSessionResponse(
            session.getId(),
            session.getOrganization().getId(),
            session.getSid(),
            session.getManagerUser() != null ? session.getManagerUser().getId() : null,
            session.getManagerDisplayName(),
            session.getProvider(),
            session.getStatus(),
            session.getRoomName(),
            session.getStageMessage(),
            resolvedWsUrl(request),
            token,
            session.getStartedAt(),
            session.getLiveAt(),
            session.getEndedAt(),
            session.getCreatedAt(),
            session.getUpdatedAt()
        );
    }

    private String managerToken(LiveSession session, User user) {
        return liveKitTokenService.managerToken(
            session.getRoomName(),
            "manager-" + user.getId() + "-sid-" + session.getSid(),
            user.getUsername()
        );
    }

    private String resolvedWsUrl(HttpServletRequest request) {
        return liveKitTokenService.resolvedWsUrl(request.getHeader("host"), request.getHeader("x-forwarded-proto") != null ? request.getHeader("x-forwarded-proto") : request.getScheme());
    }

    private Instant toInstant(Object value) {
        if (value instanceof Instant instant) return instant;
        if (value instanceof String text && !text.isBlank()) return Instant.parse(text.replace(" ", "T") + (text.endsWith("Z") ? "" : "Z")).minusSeconds(0);
        return null;
    }

    private void publishLiveEvent(Lead lead, LiveSession session) {
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("id", session.getId());
        payload.put("sid", session.getSid());
        payload.put("status", session.getStatus());
        payload.put("managerDisplayName", session.getManagerDisplayName());
        payload.put("roomName", session.getRoomName());
        payload.put("stageMessage", session.getStageMessage());
        payload.put("liveAt", session.getLiveAt() != null ? session.getLiveAt().toString() : null);
        payload.put("endedAt", session.getEndedAt() != null ? session.getEndedAt().toString() : null);
        leadEventService.publish(lead.getOrganization(), lead.getSid(), "live_session.live", payload);
    }

    private void publishEndedEvent(Lead lead, LiveSession session) {
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("id", session.getId());
        payload.put("sid", session.getSid());
        payload.put("status", session.getStatus());
        payload.put("managerDisplayName", session.getManagerDisplayName());
        payload.put("roomName", session.getRoomName());
        payload.put("stageMessage", session.getStageMessage());
        payload.put("liveAt", session.getLiveAt() != null ? session.getLiveAt().toString() : null);
        payload.put("endedAt", session.getEndedAt() != null ? session.getEndedAt().toString() : null);
        leadEventService.publish(lead.getOrganization(), lead.getSid(), "live_session.ended", payload);
    }

    private Lead requireLead(Long orgId, String sid) {
        return leadService.findByOrganizationAndSid(orgId, sid)
            .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Lead not found"));
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

    public record LiveSessionActionRequest(String sid) {
    }

    public record LiveSessionResponse(
        Long id,
        @JsonProperty("organization_id") Long organizationId,
        String sid,
        @JsonProperty("manager_user_id") Long managerUserId,
        @JsonProperty("manager_display_name") String managerDisplayName,
        String provider,
        String status,
        @JsonProperty("room_name") String roomName,
        @JsonProperty("stage_message") String stageMessage,
        @JsonProperty("ws_url") String wsUrl,
        String token,
        @JsonProperty("started_at") Instant startedAt,
        @JsonProperty("live_at") Instant liveAt,
        @JsonProperty("ended_at") Instant endedAt,
        @JsonProperty("created_at") Instant createdAt,
        @JsonProperty("updated_at") Instant updatedAt
    ) {
    }

    public record PublicLiveSessionResponse(
        String sid,
        String status,
        @JsonProperty("manager_display_name") String managerDisplayName,
        @JsonProperty("room_name") String roomName,
        @JsonProperty("stage_message") String stageMessage,
        @JsonProperty("live_at") Instant liveAt,
        @JsonProperty("ended_at") Instant endedAt,
        @JsonProperty("ws_url") String wsUrl,
        String token
    ) {
    }
}
