package com.ace.platform.chat;

import com.ace.platform.conversation.ConversationRole;
import com.ace.platform.conversation.ConversationService;
import com.ace.platform.events.LeadEventService;
import com.ace.platform.lead.Lead;
import com.ace.platform.lead.LeadService;
import com.ace.platform.user.User;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.LinkedHashMap;
import java.util.Map;

@Service
public class TakeoverService {

    private final LeadService leadService;
    private final ConversationService conversationService;
    private final LeadEventService leadEventService;

    public TakeoverService(LeadService leadService, ConversationService conversationService, LeadEventService leadEventService) {
        this.leadService = leadService;
        this.conversationService = conversationService;
        this.leadEventService = leadEventService;
    }

    @Transactional
    public Lead startTakeover(Lead lead, User user, String openingMessage) {
        boolean newlyActivated = !lead.isTakeoverActive();
        Lead updated = leadService.activateTakeover(lead, user);
        if (newlyActivated) {
            leadEventService.publish(updated.getOrganization(), updated.getSid(), "survey.paused", Map.of(
                "sid", updated.getSid(),
                "reason", "human_takeover"
            ));
            leadEventService.publish(updated.getOrganization(), updated.getSid(), "takeover.started", Map.of(
                "sid", updated.getSid(),
                "manager", user != null ? user.getUsername() : "manager",
                "active", true
            ));
        }
        if (openingMessage != null && !openingMessage.isBlank()) {
            conversationService.appendMessage(updated, ConversationRole.STAFF, openingMessage.trim());
        }
        return updated;
    }

    @Transactional
    public Lead endTakeover(Lead lead) {
        Lead updated = leadService.endTakeover(lead);
        leadEventService.publish(updated.getOrganization(), updated.getSid(), "takeover.ended", Map.of(
            "sid", updated.getSid(),
            "active", false
        ));
        return updated;
    }

    @Transactional(readOnly = true)
    public Map<String, Object> takeoverSummary(Lead lead) {
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("sid", lead.getSid());
        payload.put("active", lead.isTakeoverActive());
        payload.put("assignedUser", lead.getAssignedUser() != null ? lead.getAssignedUser().getUsername() : null);
        payload.put("status", lead.getStatus().name());
        return payload;
    }
}
