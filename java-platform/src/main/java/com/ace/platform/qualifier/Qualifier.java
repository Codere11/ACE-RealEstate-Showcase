package com.ace.platform.qualifier;

import com.ace.platform.common.model.BaseEntity;
import com.ace.platform.organization.Organization;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

import java.time.Instant;
import java.util.List;
import java.util.Map;

@Entity
@Table(name = "qualifiers")
public class Qualifier extends BaseEntity {

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "organization_id", nullable = false)
    private Organization organization;

    @Column(name = "name", nullable = false, length = 160)
    private String name;

    @Column(name = "slug", nullable = false, length = 80)
    private String slug;

    @Column(name = "status", nullable = false, length = 20)
    private String status = "draft";

    @Column(name = "system_prompt", nullable = false, columnDefinition = "text")
    private String systemPrompt = "";

    @Column(name = "assistant_style", nullable = false, length = 255)
    private String assistantStyle = "friendly, concise, consultative";

    @Column(name = "goal_definition", nullable = false, columnDefinition = "text")
    private String goalDefinition = "";

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "field_schema", columnDefinition = "jsonb")
    private Map<String, Object> fieldSchema;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "required_fields", columnDefinition = "jsonb")
    private List<String> requiredFields;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "scoring_rules", columnDefinition = "jsonb")
    private Map<String, Object> scoringRules;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "band_thresholds", columnDefinition = "jsonb")
    private Map<String, Object> bandThresholds;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "confidence_thresholds", columnDefinition = "jsonb")
    private Map<String, Object> confidenceThresholds;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "takeover_rules", columnDefinition = "jsonb")
    private Map<String, Object> takeoverRules;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "video_offer_rules", columnDefinition = "jsonb")
    private Map<String, Object> videoOfferRules;

    @Column(name = "rag_enabled", nullable = false)
    private boolean ragEnabled;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "knowledge_source_ids", columnDefinition = "jsonb")
    private List<String> knowledgeSourceIds;

    @Column(name = "max_clarifying_questions", nullable = false)
    private int maxClarifyingQuestions = 3;

    @Column(name = "contact_capture_policy", nullable = false, length = 64)
    private String contactCapturePolicy = "when_high_intent_or_explicit";

    @Column(name = "version", nullable = false)
    private int version = 1;

    @Column(name = "version_notes", nullable = false, columnDefinition = "text")
    private String versionNotes = "";

    @Column(name = "published_at")
    private Instant publishedAt;

    protected Qualifier() {
    }

    public Qualifier(Organization organization, String name, String slug) {
        this.organization = organization;
        this.name = name;
        this.slug = slug;
    }

    public Organization getOrganization() {
        return organization;
    }

    public void setOrganization(Organization organization) {
        this.organization = organization;
    }

    public String getName() {
        return name;
    }

    public void setName(String name) {
        this.name = name;
    }

    public String getSlug() {
        return slug;
    }

    public void setSlug(String slug) {
        this.slug = slug;
    }

    public String getStatus() {
        return status;
    }

    public void setStatus(String status) {
        this.status = status;
    }

    public String getSystemPrompt() {
        return systemPrompt;
    }

    public void setSystemPrompt(String systemPrompt) {
        this.systemPrompt = systemPrompt;
    }

    public String getAssistantStyle() {
        return assistantStyle;
    }

    public void setAssistantStyle(String assistantStyle) {
        this.assistantStyle = assistantStyle;
    }

    public String getGoalDefinition() {
        return goalDefinition;
    }

    public void setGoalDefinition(String goalDefinition) {
        this.goalDefinition = goalDefinition;
    }

    public Map<String, Object> getFieldSchema() {
        return fieldSchema;
    }

    public void setFieldSchema(Map<String, Object> fieldSchema) {
        this.fieldSchema = fieldSchema;
    }

    public List<String> getRequiredFields() {
        return requiredFields;
    }

    public void setRequiredFields(List<String> requiredFields) {
        this.requiredFields = requiredFields;
    }

    public Map<String, Object> getScoringRules() {
        return scoringRules;
    }

    public void setScoringRules(Map<String, Object> scoringRules) {
        this.scoringRules = scoringRules;
    }

    public Map<String, Object> getBandThresholds() {
        return bandThresholds;
    }

    public void setBandThresholds(Map<String, Object> bandThresholds) {
        this.bandThresholds = bandThresholds;
    }

    public Map<String, Object> getConfidenceThresholds() {
        return confidenceThresholds;
    }

    public void setConfidenceThresholds(Map<String, Object> confidenceThresholds) {
        this.confidenceThresholds = confidenceThresholds;
    }

    public Map<String, Object> getTakeoverRules() {
        return takeoverRules;
    }

    public void setTakeoverRules(Map<String, Object> takeoverRules) {
        this.takeoverRules = takeoverRules;
    }

    public Map<String, Object> getVideoOfferRules() {
        return videoOfferRules;
    }

    public void setVideoOfferRules(Map<String, Object> videoOfferRules) {
        this.videoOfferRules = videoOfferRules;
    }

    public boolean isRagEnabled() {
        return ragEnabled;
    }

    public void setRagEnabled(boolean ragEnabled) {
        this.ragEnabled = ragEnabled;
    }

    public List<String> getKnowledgeSourceIds() {
        return knowledgeSourceIds;
    }

    public void setKnowledgeSourceIds(List<String> knowledgeSourceIds) {
        this.knowledgeSourceIds = knowledgeSourceIds;
    }

    public int getMaxClarifyingQuestions() {
        return maxClarifyingQuestions;
    }

    public void setMaxClarifyingQuestions(int maxClarifyingQuestions) {
        this.maxClarifyingQuestions = maxClarifyingQuestions;
    }

    public String getContactCapturePolicy() {
        return contactCapturePolicy;
    }

    public void setContactCapturePolicy(String contactCapturePolicy) {
        this.contactCapturePolicy = contactCapturePolicy;
    }

    public int getVersion() {
        return version;
    }

    public void setVersion(int version) {
        this.version = version;
    }

    public String getVersionNotes() {
        return versionNotes;
    }

    public void setVersionNotes(String versionNotes) {
        this.versionNotes = versionNotes;
    }

    public Instant getPublishedAt() {
        return publishedAt;
    }

    public void setPublishedAt(Instant publishedAt) {
        this.publishedAt = publishedAt;
    }
}
