package com.ace.platform.lead;

import com.ace.platform.common.model.BaseEntity;
import com.ace.platform.organization.Organization;
import com.ace.platform.user.User;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
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
@Table(name = "leads")
public class Lead extends BaseEntity {

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "organization_id", nullable = false)
    private Organization organization;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "assigned_user_id")
    private User assignedUser;

    @Column(name = "sid", nullable = false, length = 120)
    private String sid;

    @Column(name = "display_name", nullable = false, length = 200)
    private String displayName;

    @Column(name = "email", length = 255)
    private String email;

    @Column(name = "phone", length = 120)
    private String phone;

    @Enumerated(EnumType.STRING)
    @Column(name = "status", nullable = false, length = 50)
    private LeadStatus status = LeadStatus.SURVEY;

    @Column(name = "survey_slug", length = 120)
    private String surveySlug;

    @Column(name = "survey_progress", nullable = false)
    private int surveyProgress;

    @Column(name = "last_message_preview", length = 500)
    private String lastMessagePreview;

    @Column(name = "last_message_at")
    private Instant lastMessageAt;

    @Column(name = "takeover_active", nullable = false)
    private boolean takeoverActive;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "qualifier_profile", columnDefinition = "jsonb")
    private Map<String, Object> qualifierProfile;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "qualifier_missing_fields", columnDefinition = "jsonb")
    private List<String> qualifierMissingFields;

    @Column(name = "qualification_score")
    private Integer qualificationScore;

    @Column(name = "qualification_band", length = 16)
    private String qualificationBand;

    @Column(name = "confidence_overall")
    private Double confidenceOverall;

    @Column(name = "qualification_reasoning", columnDefinition = "text")
    private String qualificationReasoning;

    @Column(name = "takeover_eligible", nullable = false)
    private boolean takeoverEligible;

    @Column(name = "video_offer_eligible", nullable = false)
    private boolean videoOfferEligible;

    protected Lead() {
    }

    public Lead(Organization organization, String sid, String displayName, String surveySlug) {
        this.organization = organization;
        this.sid = sid;
        this.displayName = displayName;
        this.surveySlug = surveySlug;
        this.status = LeadStatus.SURVEY;
        this.surveyProgress = 0;
    }

    public Organization getOrganization() {
        return organization;
    }

    public void setOrganization(Organization organization) {
        this.organization = organization;
    }

    public User getAssignedUser() {
        return assignedUser;
    }

    public void setAssignedUser(User assignedUser) {
        this.assignedUser = assignedUser;
    }

    public String getSid() {
        return sid;
    }

    public void setSid(String sid) {
        this.sid = sid;
    }

    public String getDisplayName() {
        return displayName;
    }

    public void setDisplayName(String displayName) {
        this.displayName = displayName;
    }

    public String getEmail() {
        return email;
    }

    public void setEmail(String email) {
        this.email = email;
    }

    public String getPhone() {
        return phone;
    }

    public void setPhone(String phone) {
        this.phone = phone;
    }

    public LeadStatus getStatus() {
        return status;
    }

    public void setStatus(LeadStatus status) {
        this.status = status;
    }

    public String getSurveySlug() {
        return surveySlug;
    }

    public void setSurveySlug(String surveySlug) {
        this.surveySlug = surveySlug;
    }

    public int getSurveyProgress() {
        return surveyProgress;
    }

    public void setSurveyProgress(int surveyProgress) {
        this.surveyProgress = surveyProgress;
    }

    public String getLastMessagePreview() {
        return lastMessagePreview;
    }

    public void setLastMessagePreview(String lastMessagePreview) {
        this.lastMessagePreview = lastMessagePreview;
    }

    public Instant getLastMessageAt() {
        return lastMessageAt;
    }

    public void setLastMessageAt(Instant lastMessageAt) {
        this.lastMessageAt = lastMessageAt;
    }

    public boolean isTakeoverActive() {
        return takeoverActive;
    }

    public void setTakeoverActive(boolean takeoverActive) {
        this.takeoverActive = takeoverActive;
    }

    public Map<String, Object> getQualifierProfile() {
        return qualifierProfile;
    }

    public void setQualifierProfile(Map<String, Object> qualifierProfile) {
        this.qualifierProfile = qualifierProfile;
    }

    public List<String> getQualifierMissingFields() {
        return qualifierMissingFields;
    }

    public void setQualifierMissingFields(List<String> qualifierMissingFields) {
        this.qualifierMissingFields = qualifierMissingFields;
    }

    public Integer getQualificationScore() {
        return qualificationScore;
    }

    public void setQualificationScore(Integer qualificationScore) {
        this.qualificationScore = qualificationScore;
    }

    public String getQualificationBand() {
        return qualificationBand;
    }

    public void setQualificationBand(String qualificationBand) {
        this.qualificationBand = qualificationBand;
    }

    public Double getConfidenceOverall() {
        return confidenceOverall;
    }

    public void setConfidenceOverall(Double confidenceOverall) {
        this.confidenceOverall = confidenceOverall;
    }

    public String getQualificationReasoning() {
        return qualificationReasoning;
    }

    public void setQualificationReasoning(String qualificationReasoning) {
        this.qualificationReasoning = qualificationReasoning;
    }

    public boolean isTakeoverEligible() {
        return takeoverEligible;
    }

    public void setTakeoverEligible(boolean takeoverEligible) {
        this.takeoverEligible = takeoverEligible;
    }

    public boolean isVideoOfferEligible() {
        return videoOfferEligible;
    }

    public void setVideoOfferEligible(boolean videoOfferEligible) {
        this.videoOfferEligible = videoOfferEligible;
    }
}
