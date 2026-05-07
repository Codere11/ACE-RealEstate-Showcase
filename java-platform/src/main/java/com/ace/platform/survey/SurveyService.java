package com.ace.platform.survey;

import com.ace.platform.organization.Organization;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

import java.time.Instant;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;

@Service
public class SurveyService {

    private final SurveyRepository surveyRepository;
    private final SurveyQuestionRepository surveyQuestionRepository;

    public SurveyService(SurveyRepository surveyRepository, SurveyQuestionRepository surveyQuestionRepository) {
        this.surveyRepository = surveyRepository;
        this.surveyQuestionRepository = surveyQuestionRepository;
    }

    @Transactional(readOnly = true)
    public List<Survey> listForOrganization(Long organizationId) {
        return surveyRepository.findByOrganizationIdOrderByUpdatedAtDescCreatedAtDesc(organizationId);
    }

    @Transactional(readOnly = true)
    public Survey getSurvey(Long organizationId, Long surveyId) {
        return surveyRepository.findByIdAndOrganizationId(surveyId, organizationId)
            .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Survey not found"));
    }

    @Transactional(readOnly = true)
    public SurveyDefinition getSurveyDefinition(Long organizationId, Long surveyId) {
        return toDefinition(getSurvey(organizationId, surveyId));
    }

    @Transactional(readOnly = true)
    public SurveyDefinition getPublicSurveyDefinition(Organization organization, String surveySlug) {
        String effectiveSlug = normalizeSlug(surveySlug);
        Survey survey = surveyRepository.findByOrganizationIdAndSlug(organization.getId(), effectiveSlug)
            .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Survey not found"));
        if (!survey.isActive() || !survey.isPublished()) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "Survey not published");
        }
        return toDefinition(survey);
    }

    @Transactional
    public Survey createSurvey(Organization organization, String title, String slug, String description, boolean active) {
        String normalizedTitle = normalizeTitle(title);
        String normalizedSlug = normalizeSlug(slug);
        if (surveyRepository.existsByOrganizationIdAndSlug(organization.getId(), normalizedSlug)) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "Another survey already uses that slug");
        }
        Survey survey = new Survey(organization, normalizedTitle, normalizedSlug, normalizeOptional(description), active);
        return surveyRepository.save(survey);
    }

    @Transactional
    public Survey updateSurvey(Organization organization, Long surveyId, String title, String slug, String description, boolean active) {
        Survey survey = getSurvey(organization.getId(), surveyId);
        String normalizedTitle = normalizeTitle(title);
        String normalizedSlug = normalizeSlug(slug);
        if (surveyRepository.existsByOrganizationIdAndSlugAndIdNot(organization.getId(), normalizedSlug, surveyId)) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "Another survey already uses that slug");
        }
        survey.setTitle(normalizedTitle);
        survey.setSlug(normalizedSlug);
        survey.setDescription(normalizeOptional(description));
        survey.setActive(active);
        return surveyRepository.save(survey);
    }

    @Transactional
    public Survey setPublished(Organization organization, Long surveyId, boolean published) {
        Survey survey = getSurvey(organization.getId(), surveyId);
        survey.setPublished(published);
        survey.setPublishedAt(published ? Instant.now() : null);
        return surveyRepository.save(survey);
    }

    @Transactional
    public void deleteSurvey(Organization organization, Long surveyId) {
        Survey survey = getSurvey(organization.getId(), surveyId);
        surveyRepository.delete(survey);
    }

    @Transactional
    public SurveyQuestion addQuestion(Organization organization, Long surveyId, SurveyQuestionType type, String title, String description, String placeholder, boolean required, List<String> options) {
        Survey survey = getSurvey(organization.getId(), surveyId);
        int nextOrder = surveyQuestionRepository.findBySurveyIdOrderByOrderIndexAscIdAsc(survey.getId()).size() + 1;
        SurveyQuestion question = new SurveyQuestion(
            survey,
            nextOrder,
            requireType(type),
            normalizeQuestionTitle(title),
            normalizeOptional(description),
            normalizeOptional(placeholder),
            required
        );
        applyOptions(question, options);
        return surveyQuestionRepository.save(question);
    }

    @Transactional
    public SurveyQuestion updateQuestion(Organization organization, Long surveyId, Long questionId, SurveyQuestionType type, String title, String description, String placeholder, boolean required, Integer targetOrder, List<String> options) {
        Survey survey = getSurvey(organization.getId(), surveyId);
        SurveyQuestion question = surveyQuestionRepository.findByIdAndSurveyId(questionId, surveyId)
            .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Survey question not found"));

        question.setQuestionType(requireType(type));
        question.setTitle(normalizeQuestionTitle(title));
        question.setDescription(normalizeOptional(description));
        question.setPlaceholder(normalizeOptional(placeholder));
        question.setRequired(required);
        applyOptions(question, options);
        surveyQuestionRepository.save(question);

        if (targetOrder != null) {
            reorderQuestions(survey, question, targetOrder);
        }
        return surveyQuestionRepository.findById(question.getId()).orElse(question);
    }

    @Transactional
    public void deleteQuestion(Organization organization, Long surveyId, Long questionId) {
        Survey survey = getSurvey(organization.getId(), surveyId);
        SurveyQuestion question = surveyQuestionRepository.findByIdAndSurveyId(questionId, surveyId)
            .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Survey question not found"));
        surveyQuestionRepository.delete(question);
        normalizeQuestionOrder(survey);
    }

    @Transactional
    public Survey ensureDefaultSurvey(Organization organization) {
        return surveyRepository.findByOrganizationIdAndSlug(organization.getId(), "start")
            .orElseGet(() -> {
                Survey survey = surveyRepository.save(new Survey(
                    organization,
                    "Property intake survey",
                    "start",
                    "Default public-facing survey for visitor qualification.",
                    true
                ));
                SurveyQuestion q1 = new SurveyQuestion(survey, 1, SurveyQuestionType.SINGLE_CHOICE, "What kind of property are you interested in?", "", "", true);
                applyOptions(q1, List.of("Buying a home", "Selling a property", "Renting", "Just exploring options"));
                SurveyQuestion q2 = new SurveyQuestion(survey, 2, SurveyQuestionType.SHORT_TEXT, "What location or area do you have in mind?", "", "Ljubljana, Maribor, coast…", true);
                SurveyQuestion q3 = new SurveyQuestion(survey, 3, SurveyQuestionType.SHORT_TEXT, "What budget or price range are you targeting?", "", "For example: up to 400k", true);
                SurveyQuestion q4 = new SurveyQuestion(survey, 4, SurveyQuestionType.SHORT_TEXT, "What is your ideal timeline?", "", "For example: within 3 months", true);
                surveyQuestionRepository.saveAll(List.of(q1, q2, q3, q4));
                survey.setPublished(true);
                survey.setPublishedAt(Instant.now());
                return surveyRepository.save(survey);
            });
    }

    @Transactional(readOnly = true)
    public SurveyDefinition ensureDefaultSurveyDefinition(Organization organization, String surveySlug) {
        if (surveySlug == null || surveySlug.isBlank() || "start".equalsIgnoreCase(surveySlug)) {
            Survey survey = ensureDefaultSurvey(organization);
            return toDefinition(surveyRepository.findById(survey.getId()).orElse(survey));
        }
        return getPublicSurveyDefinition(organization, surveySlug);
    }

    private SurveyDefinition toDefinition(Survey survey) {
        List<QuestionDefinition> questions = surveyQuestionRepository.findBySurveyIdOrderByOrderIndexAscIdAsc(survey.getId()).stream()
            .map(question -> new QuestionDefinition(
                question.getId(),
                question.getOrderIndex(),
                question.getQuestionType(),
                question.getTitle(),
                question.getDescription(),
                question.getPlaceholder(),
                question.isRequired(),
                question.getOptions().stream()
                    .sorted(Comparator.comparingInt(SurveyQuestionOption::getOrderIndex).thenComparing(SurveyQuestionOption::getId))
                    .map(option -> new QuestionOptionDefinition(option.getId(), option.getOrderIndex(), option.getLabel(), option.getValue()))
                    .toList()
            ))
            .toList();
        return new SurveyDefinition(
            survey.getId(),
            survey.getTitle(),
            survey.getSlug(),
            survey.getDescription(),
            survey.isActive(),
            survey.isPublished(),
            questions
        );
    }

    private void reorderQuestions(Survey survey, SurveyQuestion question, Integer targetOrder) {
        List<SurveyQuestion> ordered = new ArrayList<>(surveyQuestionRepository.findBySurveyIdOrderByOrderIndexAscIdAsc(survey.getId()));
        ordered.removeIf(item -> item.getId().equals(question.getId()));
        int desiredIndex = Math.max(0, Math.min((targetOrder == null ? question.getOrderIndex() : targetOrder) - 1, ordered.size()));
        ordered.add(desiredIndex, question);
        for (int i = 0; i < ordered.size(); i++) {
            ordered.get(i).setOrderIndex(i + 1);
        }
        surveyQuestionRepository.saveAll(ordered);
    }

    private void normalizeQuestionOrder(Survey survey) {
        List<SurveyQuestion> ordered = surveyQuestionRepository.findBySurveyIdOrderByOrderIndexAscIdAsc(survey.getId());
        for (int i = 0; i < ordered.size(); i++) {
            ordered.get(i).setOrderIndex(i + 1);
        }
        surveyQuestionRepository.saveAll(ordered);
    }

    private void applyOptions(SurveyQuestion question, List<String> rawOptions) {
        question.getOptions().clear();
        if (question.getQuestionType() != SurveyQuestionType.SINGLE_CHOICE) {
            return;
        }
        List<String> options = normalizeOptions(rawOptions);
        if (options.size() < 2) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Single choice questions require at least two options");
        }
        for (int i = 0; i < options.size(); i++) {
            String option = options.get(i);
            question.getOptions().add(new SurveyQuestionOption(question, i + 1, option, option));
        }
    }

    private List<String> normalizeOptions(List<String> rawOptions) {
        if (rawOptions == null) {
            return List.of();
        }
        Set<String> unique = new LinkedHashSet<>();
        for (String option : rawOptions) {
            String normalized = normalizeOptional(option);
            if (normalized != null) {
                unique.add(normalized);
            }
        }
        return List.copyOf(unique);
    }

    private SurveyQuestionType requireType(SurveyQuestionType type) {
        if (type == null) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Question type is required");
        }
        return type;
    }

    private String normalizeTitle(String value) {
        String normalized = normalizeOptional(value);
        if (normalized == null) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Survey title is required");
        }
        return normalized;
    }

    private String normalizeQuestionTitle(String value) {
        String normalized = normalizeOptional(value);
        if (normalized == null) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Question title is required");
        }
        return normalized;
    }

    private String normalizeSlug(String value) {
        String normalized = value == null ? "" : value.trim().toLowerCase(Locale.ROOT)
            .replaceAll("[^a-z0-9-]+", "-")
            .replaceAll("-+", "-")
            .replaceAll("^-|-$", "");
        if (normalized.isBlank()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Survey slug is required");
        }
        return normalized;
    }

    private String normalizeOptional(String value) {
        if (value == null) {
            return null;
        }
        String normalized = value.trim();
        return normalized.isBlank() ? null : normalized;
    }

    public record SurveyDefinition(
        Long id,
        String title,
        String slug,
        String description,
        boolean active,
        boolean published,
        List<QuestionDefinition> questions
    ) {
    }

    public record QuestionDefinition(
        Long id,
        int orderIndex,
        SurveyQuestionType questionType,
        String title,
        String description,
        String placeholder,
        boolean required,
        List<QuestionOptionDefinition> options
    ) {
    }

    public record QuestionOptionDefinition(
        Long id,
        int orderIndex,
        String label,
        String value
    ) {
    }
}
