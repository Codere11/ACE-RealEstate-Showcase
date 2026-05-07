package com.ace.platform.chat;

import com.ace.platform.conversation.ConversationRole;
import com.ace.platform.conversation.ConversationService;
import com.ace.platform.lead.Lead;
import com.ace.platform.lead.LeadService;
import com.ace.platform.lead.LeadStatus;
import com.ace.platform.organization.Organization;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

@Service
public class PublicChatService {

    private static final List<String> FIRST_STEP_CHOICES = List.of(
        "Buying a home",
        "Selling a property",
        "Renting",
        "Just exploring options"
    );

    private final LeadService leadService;
    private final ConversationService conversationService;

    public PublicChatService(LeadService leadService, ConversationService conversationService) {
        this.leadService = leadService;
        this.conversationService = conversationService;
    }

    @Transactional
    public ChatResult handleVisitorMessage(Organization organization, String sid, String surveySlug, String message) {
        Lead lead = leadService.getOrCreateLead(organization, sid, surveySlug);
        String trimmed = message == null ? "" : message.trim();
        if (trimmed.isBlank()) {
            return ChatResult.empty(lead.getSid(), lead.getSurveyProgress(), lead.isTakeoverActive());
        }

        conversationService.appendMessage(lead, ConversationRole.USER, trimmed);
        leadService.captureContactHints(lead, trimmed);

        if (lead.isTakeoverActive()) {
            return ChatResult.humanMode(lead.getSid(), lead.getSurveyProgress());
        }

        long userCount = conversationService.countUserMessages(lead);
        int progress = switch ((int) userCount) {
            case 1 -> 20;
            case 2 -> 40;
            case 3 -> 60;
            case 4 -> 80;
            default -> 100;
        };
        leadService.updateSurveyProgress(lead, progress);
        if (progress >= 100) {
            lead.setStatus(LeadStatus.OPEN_CHAT);
        }

        String reply = buildReply(trimmed, userCount);
        conversationService.appendMessage(lead, ConversationRole.ASSISTANT, reply);

        return new ChatResult(
            lead.getSid(),
            reply,
            progress >= 100 ? "open" : "guided",
            progress >= 100,
            progress,
            !lead.isTakeoverActive(),
            FIRST_STEP_CHOICES
        );
    }

    private String buildReply(String message, long userCount) {
        if (userCount == 1) {
            String normalized = message.toLowerCase();
            if (normalized.contains("buy")) {
                return "Great — are you looking for an apartment, a house, or land?";
            }
            if (normalized.contains("sell")) {
                return "Understood — what type of property are you selling, and in which area?";
            }
            if (normalized.contains("rent")) {
                return "Got it — what kind of rental are you searching for and in which location?";
            }
            return "Thanks — tell us what kind of property you are interested in and the general area you have in mind.";
        }
        if (userCount == 2) {
            return "Helpful. What budget range or price target are you working with?";
        }
        if (userCount == 3) {
            return "Good. What is your ideal timeline for moving forward?";
        }
        if (userCount == 4) {
            return "Perfect. Please share your preferred contact details so a manager can continue if needed.";
        }
        return "Thanks — your lead is now active in the dashboard, and a team member can take over from here if needed.";
    }

    public record ChatResult(
        String sid,
        String reply,
        String chatMode,
        boolean storyComplete,
        int surveyProgress,
        boolean choicesVisible,
        List<String> suggestedChoices
    ) {
        static ChatResult empty(String sid, int progress, boolean takeoverActive) {
            return new ChatResult(sid, null, takeoverActive ? "open" : "guided", false, progress, !takeoverActive, FIRST_STEP_CHOICES);
        }

        static ChatResult humanMode(String sid, int progress) {
            return new ChatResult(sid, null, "open", false, progress, false, List.of());
        }
    }
}
