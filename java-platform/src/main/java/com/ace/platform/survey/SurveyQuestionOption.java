package com.ace.platform.survey;

import com.ace.platform.common.model.BaseEntity;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;

@Entity
@Table(name = "survey_question_options")
public class SurveyQuestionOption extends BaseEntity {

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "question_id", nullable = false)
    private SurveyQuestion question;

    @Column(name = "order_index", nullable = false)
    private int orderIndex;

    @Column(name = "label", nullable = false, length = 500)
    private String label;

    @Column(name = "value", nullable = false, length = 500)
    private String value;

    protected SurveyQuestionOption() {
    }

    public SurveyQuestionOption(SurveyQuestion question, int orderIndex, String label, String value) {
        this.question = question;
        this.orderIndex = orderIndex;
        this.label = label;
        this.value = value;
    }

    public SurveyQuestion getQuestion() {
        return question;
    }

    public void setQuestion(SurveyQuestion question) {
        this.question = question;
    }

    public int getOrderIndex() {
        return orderIndex;
    }

    public void setOrderIndex(int orderIndex) {
        this.orderIndex = orderIndex;
    }

    public String getLabel() {
        return label;
    }

    public void setLabel(String label) {
        this.label = label;
    }

    public String getValue() {
        return value;
    }

    public void setValue(String value) {
        this.value = value;
    }
}
