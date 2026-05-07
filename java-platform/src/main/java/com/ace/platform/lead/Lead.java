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

import java.time.Instant;

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
}
