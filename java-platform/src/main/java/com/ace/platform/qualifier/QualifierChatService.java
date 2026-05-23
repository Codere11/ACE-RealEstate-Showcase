package com.ace.platform.qualifier;

import com.ace.platform.conversation.ConversationRole;
import com.ace.platform.conversation.ConversationService;
import com.ace.platform.lead.Lead;
import com.ace.platform.lead.LeadService;
import com.ace.platform.organization.Organization;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@Service
public class QualifierChatService {

    private final QualifierService qualifierService;
    private final LeadService leadService;
    private final ConversationService conversationService;
    private final PythonQualifierRuntimeClient pythonQualifierRuntimeClient;

    public QualifierChatService(
        QualifierService qualifierService,
        LeadService leadService,
        ConversationService conversationService,
        PythonQualifierRuntimeClient pythonQualifierRuntimeClient
    ) {
        this.qualifierService = qualifierService;
        this.leadService = leadService;
        this.conversationService = conversationService;
        this.pythonQualifierRuntimeClient = pythonQualifierRuntimeClient;
    }

    @Transactional
    public QualifierChatResult bootstrapState(Organization organization, String sid) {
        Lead lead = leadService.getOrCreateLead(organization, sid, null);
        lead = leadService.markOpenChat(lead);
        Qualifier qualifier = qualifierService.findActive(organization.getId()).orElse(null);
        String greeting = qualifier != null ? initialGreeting(qualifier) : "Dober dan! Dobrodošli v Lepota \u0026 Sprostitev. 💆‍♀️ Kako vam lahko danes pomagam pri negi vaše kože?";
        return new QualifierChatResult(lead.getSid(), greeting, qualifier != null ? qualifier.getName() : "AI Receptor");
    }

    @Transactional
    public QualifierChatResult handleVisitorMessage(Organization organization, String sid, String message, Map<String, Object> spatialContext) {
        Lead lead = leadService.getOrCreateLead(organization, sid, null);
        lead = leadService.markOpenChat(lead);
        Qualifier qualifier = qualifierService.findActive(organization.getId()).orElse(null);
        String trimmed = message == null ? "" : message.trim();
        if (trimmed.isBlank()) {
            return bootstrapState(organization, lead.getSid());
        }

        conversationService.appendMessage(lead, ConversationRole.USER, trimmed);
        leadService.captureContactHints(lead, trimmed);

        if (lead.isTakeoverActive()) {
            return new QualifierChatResult(lead.getSid(), null, qualifier != null ? qualifier.getName() : "AI Receptor");
        }

        if (qualifier == null) {
            return new QualifierChatResult(lead.getSid(), null, "AI Receptor");
        }

        PythonQualifierRuntimeClient.RuntimeResponse response = pythonQualifierRuntimeClient.evaluate(
            new PythonQualifierRuntimeClient.RuntimeRequest(
                lead.getSid(),
                trimmed,
                qualifierPayload(qualifier),
                recentMessages(lead),
                lead.getQualifierProfile() != null ? lead.getQualifierProfile() : Map.of(),
                spatialContext
            )
        );

        leadService.applyQualifierResult(
            lead,
            response.safeProfile(),
            response.safeMissingFields(),
            response.qualificationScore(),
            response.qualificationBand(),
            response.confidenceOverall(),
            response.reasoning(),
            response.takeoverEligible(),
            response.videoOfferEligible()
        );

        String reply = response.reply();
        if (reply != null && !reply.isBlank()) {
            conversationService.appendMessage(lead, ConversationRole.ASSISTANT, reply);
        }
        return new QualifierChatResult(lead.getSid(), reply, qualifier.getName());
    }

    private String initialGreeting(Qualifier qualifier) {
        return "Dober dan! Dobrodošli v Lepota \u0026 Sprostitev. 💆‍♀️ Kako vam lahko danes pomagam pri negi vaše kože?";
    }

    private List<Map<String, String>> recentMessages(Lead lead) {
        List<com.ace.platform.conversation.ConversationMessage> thread = conversationService.getThread(lead);
        int from = Math.max(0, thread.size() - 8);
        return thread.subList(from, thread.size()).stream()
            .map(message -> Map.of(
                "role", message.getRole().apiValue(),
                "text", message.getText() != null ? message.getText() : ""
            ))
            .toList();
    }

    private Map<String, Object> qualifierPayload(Qualifier qualifier) {
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("name", qualifier.getName());
        payload.put("slug", qualifier.getSlug());
        payload.put("status", qualifier.getStatus());
        payload.put("system_prompt", qualifier.getSystemPrompt());
        payload.put("assistant_style", qualifier.getAssistantStyle());
        payload.put("goal_definition", qualifier.getGoalDefinition());
        payload.put("field_schema", qualifier.getFieldSchema());
        payload.put("required_fields", qualifier.getRequiredFields());
        payload.put("scoring_rules", qualifier.getScoringRules());
        payload.put("band_thresholds", qualifier.getBandThresholds());
        payload.put("confidence_thresholds", qualifier.getConfidenceThresholds());
        payload.put("takeover_rules", qualifier.getTakeoverRules());
        payload.put("video_offer_rules", qualifier.getVideoOfferRules());
        payload.put("rag_enabled", qualifier.isRagEnabled());
        payload.put("knowledge_source_ids", qualifier.getKnowledgeSourceIds());
        payload.put("max_clarifying_questions", qualifier.getMaxClarifyingQuestions());
        payload.put("contact_capture_policy", qualifier.getContactCapturePolicy());
        payload.put("version", qualifier.getVersion());
        payload.put("version_notes", qualifier.getVersionNotes());
        return payload;
    }

    public record QualifierChatResult(String sid, String reply, String qualifierName) {
    }
}
