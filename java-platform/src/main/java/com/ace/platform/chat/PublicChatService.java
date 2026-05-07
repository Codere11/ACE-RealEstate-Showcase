package com.ace.platform.chat;

import com.ace.platform.conversation.ConversationRole;
import com.ace.platform.conversation.ConversationService;
import com.ace.platform.lead.Lead;
import com.ace.platform.lead.LeadService;
import com.ace.platform.lead.LeadStatus;
import com.ace.platform.organization.Organization;
import com.ace.platform.survey.SurveyQuestionType;
import com.ace.platform.survey.SurveyService;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

@Service
public class PublicChatService {

    private final LeadService leadService;
    private final ConversationService conversationService;
    private final SurveyService surveyService;

    public PublicChatService(LeadService leadService, ConversationService conversationService, SurveyService surveyService) {
        this.leadService = leadService;
        this.conversationService = conversationService;
        this.surveyService = surveyService;
    }

    @Transactional
    public ChatResult handleVisitorMessage(Organization organization, String sid, String surveySlug, String message) {
        Lead lead = leadService.getOrCreateLead(organization, sid, surveySlug);
        SurveyService.SurveyDefinition survey = surveyService.ensureDefaultSurveyDefinition(organization, surveySlug);
        String trimmed = message == null ? "" : message.trim();
        if (trimmed.isBlank()) {
            return bootstrapState(organization, lead.getSid(), survey.slug());
        }

        conversationService.appendMessage(lead, ConversationRole.USER, trimmed);
        leadService.captureContactHints(lead, trimmed);

        if (lead.isTakeoverActive()) {
            return ChatResult.humanMode(lead.getSid(), lead.getSurveyProgress());
        }

        long userCount = conversationService.countUserMessages(lead);
        int progress = progressFor(userCount, survey.questions().size());
        leadService.updateSurveyProgress(lead, progress);
        if (progress >= 100) {
            lead.setStatus(LeadStatus.OPEN_CHAT);
        }

        SurveyStep nextStep = nextStep(survey, userCount);
        boolean complete = nextStep == null;
        return new ChatResult(
            lead.getSid(),
            null,
            complete ? "open" : "guided",
            complete,
            progress,
            nextStep,
            complete ? "Thanks — your information has been received." : null,
            complete ? "A team member can continue from here when needed." : null
        );
    }

    @Transactional
    public ChatResult bootstrapState(Organization organization, String sid, String surveySlug) {
        Lead lead = leadService.getOrCreateLead(organization, sid, surveySlug);
        SurveyService.SurveyDefinition survey = surveyService.ensureDefaultSurveyDefinition(organization, surveySlug);
        long userCount = conversationService.countUserMessages(lead);
        int progress = progressFor(userCount, survey.questions().size());
        if (lead.getSurveyProgress() != progress) {
            leadService.updateSurveyProgress(lead, progress);
        }
        SurveyStep nextStep = lead.isTakeoverActive() ? null : nextStep(survey, userCount);
        boolean complete = nextStep == null;
        return new ChatResult(
            lead.getSid(),
            null,
            lead.isTakeoverActive() || complete ? "open" : "guided",
            complete,
            progress,
            nextStep,
            complete && !lead.isTakeoverActive() ? "Thanks — your information has been received." : null,
            complete && !lead.isTakeoverActive() ? "A team member can continue from here when needed." : null
        );
    }

    private int progressFor(long answeredCount, int totalQuestions) {
        if (totalQuestions <= 0) {
            return 100;
        }
        return (int) Math.max(0, Math.min(100, Math.round((answeredCount * 100.0f) / totalQuestions)));
    }

    private SurveyStep nextStep(SurveyService.SurveyDefinition survey, long answeredCount) {
        if (answeredCount >= survey.questions().size()) {
            return null;
        }
        SurveyService.QuestionDefinition question = survey.questions().get((int) answeredCount);
        return new SurveyStep(
            question.orderIndex(),
            question.questionType().name(),
            question.title(),
            question.description(),
            question.placeholder(),
            question.options().stream().map(SurveyService.QuestionOptionDefinition::label).toList()
        );
    }

    public record ChatResult(
        String sid,
        String reply,
        String chatMode,
        boolean storyComplete,
        int surveyProgress,
        SurveyStep currentStep,
        String completionTitle,
        String completionSubtitle
    ) {
        static ChatResult humanMode(String sid, int progress) {
            return new ChatResult(sid, null, "open", false, progress, null, null, null);
        }
    }

    public record SurveyStep(
        int orderIndex,
        String questionType,
        String title,
        String description,
        String placeholder,
        List<String> options
    ) {
        public boolean singleChoice() {
            return SurveyQuestionType.SINGLE_CHOICE.name().equals(questionType);
        }
    }
}
