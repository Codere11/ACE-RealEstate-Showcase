package com.ace.platform.live;

import com.ace.platform.organization.Organization;
import com.ace.platform.user.User;
import org.springframework.context.annotation.Profile;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Optional;

@Service
@Profile("!test")
public class LiveSessionService {

    private final LiveSessionRepository liveSessionRepository;

    public LiveSessionService(LiveSessionRepository liveSessionRepository) {
        this.liveSessionRepository = liveSessionRepository;
    }

    @Transactional(readOnly = true)
    public Optional<LiveSession> getCurrent(Long organizationId, String sid) {
        return liveSessionRepository.findFirstByOrganizationIdAndSidOrderByCreatedAtDescIdDesc(organizationId, sid);
    }

    @Transactional
    public LiveSession upsertPreview(Organization organization, String sid, User managerUser, String managerDisplayName) {
        Optional<LiveSession> current = getCurrent(organization.getId(), sid);
        if (current.isPresent() && isPreviewOrLive(current.get())) {
            LiveSession session = current.get();
            session.setStatus("preview");
            session.setManagerUser(managerUser);
            session.setManagerDisplayName(managerDisplayName);
            session.setEndedAt(null);
            session.setStageMessage(managerDisplayName + " is getting ready to help live.");
            if (session.getStartedAt() == null) session.setStartedAt(Instant.now());
            return liveSessionRepository.save(session);
        }

        LiveSession session = new LiveSession(
            organization,
            sid,
            managerUser,
            managerDisplayName,
            "preview",
            roomName(organization.getId(), sid),
            managerDisplayName + " is getting ready to help live.",
            Instant.now()
        );
        return liveSessionRepository.save(session);
    }

    @Transactional
    public LiveSession goLive(Organization organization, String sid, User managerUser, String managerDisplayName) {
        LiveSession session = upsertPreview(organization, sid, managerUser, managerDisplayName);
        session.setStatus("live");
        session.setManagerUser(managerUser);
        session.setManagerDisplayName(managerDisplayName);
        session.setLiveAt(Instant.now());
        session.setEndedAt(null);
        session.setStageMessage(managerDisplayName + " is joining to help.");
        return liveSessionRepository.save(session);
    }

    @Transactional
    public Optional<LiveSession> end(Long organizationId, Long sessionId) {
        return liveSessionRepository.findByIdAndOrganizationId(sessionId, organizationId)
            .map(session -> {
                session.setStatus("ended");
                session.setEndedAt(Instant.now());
                session.setStageMessage("Live help has ended.");
                return liveSessionRepository.save(session);
            });
    }

    @Transactional(readOnly = true)
    public Map<String, Object> publicState(Long organizationId, String sid) {
        return getCurrent(organizationId, sid)
            .<Map<String, Object>>map(session -> {
                Map<String, Object> out = new LinkedHashMap<>();
                out.put("sid", sid);
                out.put("status", session.getStatus());
                out.put("manager_display_name", session.getManagerDisplayName());
                out.put("room_name", session.getRoomName());
                out.put("stage_message", session.getStageMessage());
                out.put("live_at", session.getLiveAt());
                out.put("ended_at", session.getEndedAt());
                return out;
            })
            .orElseGet(() -> {
                Map<String, Object> out = new LinkedHashMap<>();
                out.put("sid", sid);
                out.put("status", "idle");
                out.put("manager_display_name", "");
                out.put("room_name", null);
                out.put("stage_message", "");
                out.put("live_at", null);
                out.put("ended_at", null);
                return out;
            });
    }

    public String roomName(Long organizationId, String sid) {
        String safeSid = sid == null ? "sid" : sid.replaceAll("[^a-zA-Z0-9_-]", "");
        if (safeSid.isBlank()) safeSid = "sid";
        if (safeSid.length() > 48) safeSid = safeSid.substring(0, 48);
        return "org-" + organizationId + "-live-" + safeSid;
    }

    private boolean isPreviewOrLive(LiveSession session) {
        return "preview".equals(session.getStatus()) || "live".equals(session.getStatus());
    }
}
