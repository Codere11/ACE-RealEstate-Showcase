package com.ace.platform.survey;

import com.ace.platform.conversation.ConversationRole;
import com.ace.platform.conversation.ConversationService;
import com.ace.platform.lead.Lead;
import com.ace.platform.lead.LeadService;
import com.ace.platform.organization.Organization;
import com.ace.platform.organization.OrganizationRepository;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@RestController
public class SurveyCompatibilityController {

    private final OrganizationRepository organizationRepository;
    private final SurveyService surveyService;
    private final LeadService leadService;
    private final ConversationService conversationService;

    public SurveyCompatibilityController(
        OrganizationRepository organizationRepository,
        SurveyService surveyService,
        LeadService leadService,
        ConversationService conversationService
    ) {
        this.organizationRepository = organizationRepository;
        this.surveyService = surveyService;
        this.leadService = leadService;
        this.conversationService = conversationService;
    }

    @GetMapping("/s/")
    public List<Map<String, Object>> listPublicSurveys() {
        List<Map<String, Object>> out = new ArrayList<>();
        for (Organization organization : organizationRepository.findAll()) {
            if (!organization.isActive()) continue;
            Survey survey = surveyService.ensureDefaultSurvey(organization);
            if (!survey.isPublished() || !survey.isActive()) continue;
            out.add(Map.of(
                "id", survey.getId(),
                "name", survey.getTitle(),
                "slug", survey.getSlug(),
                "org_slug", organization.getSlug(),
                "survey_type", "regular",
                "published_at", survey.getPublishedAt() != null ? survey.getPublishedAt().toString() : null
            ));
        }
        return out;
    }

    @GetMapping("/s/{orgSlug}/{surveySlug}")
    public Map<String, Object> surveyBySlug(@PathVariable String orgSlug, @PathVariable String surveySlug) {
        Organization organization = organizationRepository.findBySlugAndActiveTrue(orgSlug)
            .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Organization not found"));
        SurveyService.SurveyDefinition survey = surveyService.getPublicSurveyDefinition(organization, surveySlug);
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("survey_id", survey.id());
        out.put("name", survey.title());
        out.put("slug", survey.slug());
        out.put("org_slug", organization.getSlug());
        out.put("survey_type", "regular");
        out.put("variant", null);
        out.put("flow", flowDefinition(survey));
        return out;
    }

    @PostMapping({"/chat/survey/submit", "/api/public/chat/survey/submit"})
    public Map<String, Object> submitSurveyAnswer(@RequestBody SurveySubmitRequest request) {
        Organization organization = organizationRepository.findBySlugAndActiveTrue(request.orgSlug())
            .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Organization not found"));
        SurveyService.SurveyDefinition survey = surveyService.ensureDefaultSurveyDefinition(organization, request.surveySlug());
        Lead lead = leadService.getOrCreateLead(organization, request.sid(), survey.slug());
        if (request.answer() != null) {
            String text = answerText(request.answer());
            if (!text.isBlank()) {
                conversationService.appendMessage(lead, ConversationRole.USER, text);
                leadService.touchLead(lead, text);
                leadService.captureContactHints(lead, text);
            }
        }
        leadService.updateSurveyProgress(lead, request.progress() != null ? request.progress() : 0);
        return Map.of("ok", true, "paused", false, "sid", lead.getSid(), "progress", lead.getSurveyProgress());
    }

    private Map<String, Object> flowDefinition(SurveyService.SurveyDefinition survey) {
        List<Map<String, Object>> nodes = new ArrayList<>();
        List<SurveyService.QuestionDefinition> questions = survey.questions();
        for (int i = 0; i < questions.size(); i++) {
            SurveyService.QuestionDefinition question = questions.get(i);
            String nodeId = "q" + (i + 1);
            String nextId = i + 1 < questions.size() ? "q" + (i + 2) : "contact";
            Map<String, Object> node = new LinkedHashMap<>();
            node.put("id", nodeId);
            node.put("texts", List.of(question.title()));
            if (question.questionType() == SurveyQuestionType.SINGLE_CHOICE) {
                List<Map<String, Object>> choices = new ArrayList<>();
                for (SurveyService.QuestionOptionDefinition option : question.options()) {
                    choices.add(Map.of("title", option.label(), "next", nextId));
                }
                node.put("choices", choices);
            } else {
                node.put("openInput", true);
                node.put("inputType", "text");
                node.put("next", nextId);
            }
            nodes.add(node);
        }
        nodes.add(Map.of(
            "id", "contact",
            "texts", List.of("Leave email or phone so team can reach you."),
            "openInput", true,
            "inputType", "dual-contact",
            "next", "thank_you"
        ));
        nodes.add(Map.of(
            "id", "thank_you",
            "texts", List.of("Thank you. Team will reach out soon."),
            "terminal", true
        ));
        return Map.of("start", questions.isEmpty() ? "contact" : "q1", "nodes", nodes);
    }

    private String answerText(Object answer) {
        if (answer instanceof String text) return text.trim();
        if (answer instanceof Map<?, ?> map) {
            List<String> parts = new ArrayList<>();
            Object title = map.get("title");
            Object text = map.get("text");
            Object email = map.get("email");
            Object phone = map.get("phone");
            if (title != null && !String.valueOf(title).isBlank()) parts.add(String.valueOf(title).trim());
            if (text != null && !String.valueOf(text).isBlank()) parts.add(String.valueOf(text).trim());
            if (email != null && !String.valueOf(email).isBlank()) parts.add(String.valueOf(email).trim());
            if (phone != null && !String.valueOf(phone).isBlank()) parts.add(String.valueOf(phone).trim());
            return String.join(" ", parts).trim();
        }
        return "";
    }

    public record SurveySubmitRequest(
        String sid,
        @com.fasterxml.jackson.annotation.JsonProperty("node_id") String nodeId,
        Object answer,
        Integer progress,
        @com.fasterxml.jackson.annotation.JsonProperty("all_answers") Map<String, Object> allAnswers,
        @com.fasterxml.jackson.annotation.JsonProperty("org_slug") String orgSlug,
        @com.fasterxml.jackson.annotation.JsonProperty("survey_slug") String surveySlug
    ) {
    }
}
