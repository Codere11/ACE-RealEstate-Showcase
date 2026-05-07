package com.ace.platform.survey;

import com.ace.platform.common.model.BaseEntity;
import jakarta.persistence.CascadeType;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.FetchType;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.OneToMany;
import jakarta.persistence.OrderBy;
import jakarta.persistence.Table;

import java.util.ArrayList;
import java.util.List;

@Entity
@Table(name = "survey_questions")
public class SurveyQuestion extends BaseEntity {

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "survey_id", nullable = false)
    private Survey survey;

    @Column(name = "order_index", nullable = false)
    private int orderIndex;

    @Enumerated(EnumType.STRING)
    @Column(name = "question_type", nullable = false, length = 50)
    private SurveyQuestionType questionType;

    @Column(name = "title", nullable = false, length = 500)
    private String title;

    @Column(name = "description", length = 2000)
    private String description;

    @Column(name = "placeholder", length = 500)
    private String placeholder;

    @Column(name = "required", nullable = false)
    private boolean required = true;

    @OneToMany(mappedBy = "question", cascade = CascadeType.ALL, orphanRemoval = true)
    @OrderBy("orderIndex ASC, id ASC")
    private List<SurveyQuestionOption> options = new ArrayList<>();

    protected SurveyQuestion() {
    }

    public SurveyQuestion(Survey survey, int orderIndex, SurveyQuestionType questionType, String title, String description, String placeholder, boolean required) {
        this.survey = survey;
        this.orderIndex = orderIndex;
        this.questionType = questionType;
        this.title = title;
        this.description = description;
        this.placeholder = placeholder;
        this.required = required;
    }

    public Survey getSurvey() {
        return survey;
    }

    public void setSurvey(Survey survey) {
        this.survey = survey;
    }

    public int getOrderIndex() {
        return orderIndex;
    }

    public void setOrderIndex(int orderIndex) {
        this.orderIndex = orderIndex;
    }

    public SurveyQuestionType getQuestionType() {
        return questionType;
    }

    public void setQuestionType(SurveyQuestionType questionType) {
        this.questionType = questionType;
    }

    public String getTitle() {
        return title;
    }

    public void setTitle(String title) {
        this.title = title;
    }

    public String getDescription() {
        return description;
    }

    public void setDescription(String description) {
        this.description = description;
    }

    public String getPlaceholder() {
        return placeholder;
    }

    public void setPlaceholder(String placeholder) {
        this.placeholder = placeholder;
    }

    public boolean isRequired() {
        return required;
    }

    public void setRequired(boolean required) {
        this.required = required;
    }

    public List<SurveyQuestionOption> getOptions() {
        return options;
    }
}
