package com.ace.platform.survey;

import com.ace.platform.chat.PublicChatService;
import com.ace.platform.organization.Organization;
import com.ace.platform.organization.OrganizationRepository;
import com.ace.platform.user.User;
import com.ace.platform.user.UserRepository;
import jakarta.transaction.Transactional;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

import java.util.Comparator;
import java.util.List;
import java.util.Map;

@RestController
@Transactional
public class SurveyApiController {

    private final SurveyService surveyService;
    private final UserRepository userRepository;
    private final OrganizationRepository organizationRepository;
    private final PublicChatService publicChatService;

    public SurveyApiController(SurveyService surveyService, UserRepository userRepository, OrganizationRepository organizationRepository, PublicChatService publicChatService) {
        this.surveyService = surveyService;
        this.userRepository = userRepository;
        this.organizationRepository = organizationRepository;
        this.publicChatService = publicChatService;
    }

    @GetMapping("/api/public/organizations/{orgSlug}/surveys/{surveySlug}")
    public PublicSurveyStateResponse publicSurvey(
        @PathVariable String orgSlug,
        @PathVariable String surveySlug,
        @org.springframework.web.bind.annotation.RequestParam(required = false) String sid
    ) {
        Organization organization = organizationRepository.findBySlugAndActiveTrue(orgSlug)
            .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Organization not found"));
        PublicChatService.ChatResult state = publicChatService.bootstrapState(organization, sid, surveySlug);
        SurveyService.SurveyDefinition survey = surveyService.ensureDefaultSurveyDefinition(organization, surveySlug);
        return PublicSurveyStateResponse.from(survey, state);
    }

    @GetMapping("/api/organizations/{orgId}/surveys")
    public List<SurveySummaryResponse> surveys(@PathVariable Long orgId, Authentication authentication) {
        User user = requireUser(authentication);
        requireOrgAccess(user, orgId);
        return surveyService.listForOrganization(orgId).stream().map(SurveySummaryResponse::from).toList();
    }

    @GetMapping("/api/organizations/{orgId}/surveys/{surveyId}")
    public SurveyDetailResponse survey(@PathVariable Long orgId, @PathVariable Long surveyId, Authentication authentication) {
        User user = requireUser(authentication);
        requireOrgAccess(user, orgId);
        return SurveyDetailResponse.from(surveyService.getSurvey(orgId, surveyId));
    }

    @PostMapping("/api/organizations/{orgId}/surveys")
    public SurveyDetailResponse createSurvey(@PathVariable Long orgId, @RequestBody SurveyUpsertRequest request, Authentication authentication) {
        User user = requireUser(authentication);
        requireOrgAccess(user, orgId);
        Organization organization = organizationRepository.findById(orgId)
            .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Organization not found"));
        Survey survey = surveyService.createSurvey(organization, request.title(), request.slug(), request.description(), request.active());
        return SurveyDetailResponse.from(survey);
    }

    @PutMapping("/api/organizations/{orgId}/surveys/{surveyId}")
    public SurveyDetailResponse updateSurvey(@PathVariable Long orgId, @PathVariable Long surveyId, @RequestBody SurveyUpsertRequest request, Authentication authentication) {
        User user = requireUser(authentication);
        requireOrgAccess(user, orgId);
        Organization organization = organizationRepository.findById(orgId)
            .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Organization not found"));
        Survey survey = surveyService.updateSurvey(organization, surveyId, request.title(), request.slug(), request.description(), request.active());
        return SurveyDetailResponse.from(survey);
    }

    @DeleteMapping("/api/organizations/{orgId}/surveys/{surveyId}")
    public Map<String, Object> deleteSurvey(@PathVariable Long orgId, @PathVariable Long surveyId, Authentication authentication) {
        User user = requireUser(authentication);
        requireOrgAccess(user, orgId);
        Organization organization = organizationRepository.findById(orgId)
            .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Organization not found"));
        surveyService.deleteSurvey(organization, surveyId);
        return Map.of("ok", true, "surveyId", surveyId);
    }

    @PostMapping("/api/organizations/{orgId}/surveys/{surveyId}/publish")
    public SurveyDetailResponse publishSurvey(@PathVariable Long orgId, @PathVariable Long surveyId, @RequestBody PublishRequest request, Authentication authentication) {
        User user = requireUser(authentication);
        requireOrgAccess(user, orgId);
        Organization organization = organizationRepository.findById(orgId)
            .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Organization not found"));
        Survey survey = surveyService.setPublished(organization, surveyId, request == null || request.published() == null || request.published());
        return SurveyDetailResponse.from(survey);
    }

    @PostMapping("/api/organizations/{orgId}/surveys/{surveyId}/questions")
    public SurveyQuestionResponse createQuestion(@PathVariable Long orgId, @PathVariable Long surveyId, @RequestBody QuestionUpsertRequest request, Authentication authentication) {
        User user = requireUser(authentication);
        requireOrgAccess(user, orgId);
        Organization organization = organizationRepository.findById(orgId)
            .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Organization not found"));
        SurveyQuestion question = surveyService.addQuestion(organization, surveyId, request.questionType(), request.title(), request.description(), request.placeholder(), request.required(), request.options());
        return SurveyQuestionResponse.from(question);
    }

    @PutMapping("/api/organizations/{orgId}/surveys/{surveyId}/questions/{questionId}")
    public SurveyQuestionResponse updateQuestion(@PathVariable Long orgId, @PathVariable Long surveyId, @PathVariable Long questionId, @RequestBody QuestionUpsertRequest request, Authentication authentication) {
        User user = requireUser(authentication);
        requireOrgAccess(user, orgId);
        Organization organization = organizationRepository.findById(orgId)
            .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Organization not found"));
        SurveyQuestion question = surveyService.updateQuestion(
            organization,
            surveyId,
            questionId,
            request.questionType(),
            request.title(),
            request.description(),
            request.placeholder(),
            request.required(),
            request.orderIndex(),
            request.options()
        );
        return SurveyQuestionResponse.from(question);
    }

    @DeleteMapping("/api/organizations/{orgId}/surveys/{surveyId}/questions/{questionId}")
    public Map<String, Object> deleteQuestion(@PathVariable Long orgId, @PathVariable Long surveyId, @PathVariable Long questionId, Authentication authentication) {
        User user = requireUser(authentication);
        requireOrgAccess(user, orgId);
        Organization organization = organizationRepository.findById(orgId)
            .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Organization not found"));
        surveyService.deleteQuestion(organization, surveyId, questionId);
        return Map.of("ok", true, "questionId", questionId);
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

    public record SurveyUpsertRequest(String title, String slug, String description, boolean active) {
    }

    public record PublishRequest(Boolean published) {
    }

    public record QuestionUpsertRequest(
        SurveyQuestionType questionType,
        String title,
        String description,
        String placeholder,
        boolean required,
        Integer orderIndex,
        List<String> options
    ) {
    }

    public record SurveySummaryResponse(Long id, String title, String slug, String description, boolean active, boolean published, int questionCount) {
        static SurveySummaryResponse from(Survey survey) {
            return new SurveySummaryResponse(
                survey.getId(),
                survey.getTitle(),
                survey.getSlug(),
                survey.getDescription(),
                survey.isActive(),
                survey.isPublished(),
                survey.getQuestions() != null ? survey.getQuestions().size() : 0
            );
        }
    }

    public record SurveyDetailResponse(Long id, String title, String slug, String description, boolean active, boolean published, List<SurveyQuestionResponse> questions) {
        static SurveyDetailResponse from(Survey survey) {
            List<SurveyQuestionResponse> questions = survey.getQuestions().stream()
                .sorted(Comparator.comparingInt(SurveyQuestion::getOrderIndex).thenComparing(SurveyQuestion::getId))
                .map(SurveyQuestionResponse::from)
                .toList();
            return new SurveyDetailResponse(survey.getId(), survey.getTitle(), survey.getSlug(), survey.getDescription(), survey.isActive(), survey.isPublished(), questions);
        }
    }

    public record SurveyQuestionResponse(Long id, int orderIndex, String questionType, String title, String description, String placeholder, boolean required, List<OptionResponse> options) {
        static SurveyQuestionResponse from(SurveyQuestion question) {
            return new SurveyQuestionResponse(
                question.getId(),
                question.getOrderIndex(),
                question.getQuestionType().name(),
                question.getTitle(),
                question.getDescription(),
                question.getPlaceholder(),
                question.isRequired(),
                question.getOptions().stream()
                    .sorted(Comparator.comparingInt(SurveyQuestionOption::getOrderIndex).thenComparing(SurveyQuestionOption::getId))
                    .map(option -> new OptionResponse(option.getId(), option.getOrderIndex(), option.getLabel(), option.getValue()))
                    .toList()
            );
        }
    }

    public record OptionResponse(Long id, int orderIndex, String label, String value) {
    }

    public record PublicSurveyStateResponse(
        Long id,
        String title,
        String slug,
        String description,
        String sid,
        int surveyProgress,
        boolean storyComplete,
        PublicStepResponse currentStep,
        String completionTitle,
        String completionSubtitle
    ) {
        static PublicSurveyStateResponse from(SurveyService.SurveyDefinition survey, PublicChatService.ChatResult state) {
            return new PublicSurveyStateResponse(
                survey.id(),
                survey.title(),
                survey.slug(),
                survey.description(),
                state.sid(),
                state.surveyProgress(),
                state.storyComplete(),
                state.currentStep() != null ? PublicStepResponse.from(state.currentStep()) : null,
                state.completionTitle(),
                state.completionSubtitle()
            );
        }
    }

    public record PublicStepResponse(
        int orderIndex,
        String questionType,
        String title,
        String description,
        String placeholder,
        List<String> options
    ) {
        static PublicStepResponse from(PublicChatService.SurveyStep step) {
            return new PublicStepResponse(step.orderIndex(), step.questionType(), step.title(), step.description(), step.placeholder(), step.options());
        }
    }
}
