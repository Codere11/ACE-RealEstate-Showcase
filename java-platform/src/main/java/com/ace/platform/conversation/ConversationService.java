package com.ace.platform.conversation;

import com.ace.platform.events.LeadEventService;
import com.ace.platform.lead.Lead;
import com.ace.platform.lead.LeadService;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@Service
public class ConversationService {

    private final ConversationMessageRepository conversationMessageRepository;
    private final LeadService leadService;
    private final LeadEventService leadEventService;

    public ConversationService(
        ConversationMessageRepository conversationMessageRepository,
        LeadService leadService,
        LeadEventService leadEventService
    ) {
        this.conversationMessageRepository = conversationMessageRepository;
        this.leadService = leadService;
        this.leadEventService = leadEventService;
    }

    @Transactional
    public ConversationMessage appendMessage(Lead lead, ConversationRole role, String text) {
        ConversationMessage saved = conversationMessageRepository.save(
            new ConversationMessage(lead.getOrganization(), lead, role, text)
        );
        leadService.touchLead(lead, text);
        leadEventService.publish(lead.getOrganization(), lead.getSid(), "message.created", Map.of(
            "role", role.apiValue(),
            "text", text,
            "timestamp", saved.getCreatedAt() != null ? saved.getCreatedAt().toEpochMilli() : System.currentTimeMillis()
        ));
        leadEventService.publish(lead.getOrganization(), lead.getSid(), "lead.touched", leadPayload(lead));
        return saved;
    }

    @Transactional(readOnly = true)
    public List<ConversationMessage> getThread(Lead lead) {
        return conversationMessageRepository.findByLeadIdOrderByCreatedAtAscIdAsc(lead.getId());
    }

    @Transactional(readOnly = true)
    public long countUserMessages(Lead lead) {
        return conversationMessageRepository.countByLeadIdAndRole(lead.getId(), ConversationRole.USER);
    }

    private Map<String, Object> leadPayload(Lead lead) {
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("lastMessage", lead.getLastMessagePreview());
        payload.put("lastSeenSec", lead.getLastMessageAt() != null ? lead.getLastMessageAt().getEpochSecond() : null);
        payload.put("survey_progress", lead.getSurveyProgress());
        payload.put("takeover_active", lead.isTakeoverActive());
        payload.put("status", lead.getStatus().name());
        return payload;
    }
}
