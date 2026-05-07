package com.ace.platform.survey;

import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

public interface SurveyQuestionRepository extends JpaRepository<SurveyQuestion, Long> {
    List<SurveyQuestion> findBySurveyIdOrderByOrderIndexAscIdAsc(Long surveyId);
    Optional<SurveyQuestion> findByIdAndSurveyId(Long id, Long surveyId);
    long countBySurveyId(Long surveyId);
}
