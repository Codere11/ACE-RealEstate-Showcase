package com.ace.platform.live;

import com.ace.platform.common.model.BaseEntity;
import com.ace.platform.organization.Organization;
import com.ace.platform.user.User;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;

import java.time.Instant;

@Entity
@Table(name = "live_sessions")
public class LiveSession extends BaseEntity {

    @ManyToOne(fetch = FetchType.EAGER, optional = false)
    @JoinColumn(name = "organization_id", nullable = false)
    private Organization organization;

    @Column(name = "sid", nullable = false, length = 120)
    private String sid;

    @ManyToOne(fetch = FetchType.EAGER)
    @JoinColumn(name = "manager_user_id")
    private User managerUser;

    @Column(name = "manager_display_name", nullable = false, length = 200)
    private String managerDisplayName;

    @Column(name = "provider", nullable = false, length = 50)
    private String provider = "livekit";

    @Column(name = "status", nullable = false, length = 50)
    private String status;

    @Column(name = "room_name", length = 200)
    private String roomName;

    @Column(name = "stage_message", length = 500)
    private String stageMessage;

    @Column(name = "started_at")
    private Instant startedAt;

    @Column(name = "live_at")
    private Instant liveAt;

    @Column(name = "ended_at")
    private Instant endedAt;

    protected LiveSession() {
    }

    public LiveSession(Organization organization, String sid, User managerUser, String managerDisplayName, String status, String roomName, String stageMessage, Instant startedAt) {
        this.organization = organization;
        this.sid = sid;
        this.managerUser = managerUser;
        this.managerDisplayName = managerDisplayName;
        this.status = status;
        this.roomName = roomName;
        this.stageMessage = stageMessage;
        this.startedAt = startedAt;
    }

    public Organization getOrganization() {
        return organization;
    }

    public void setOrganization(Organization organization) {
        this.organization = organization;
    }

    public String getSid() {
        return sid;
    }

    public void setSid(String sid) {
        this.sid = sid;
    }

    public User getManagerUser() {
        return managerUser;
    }

    public void setManagerUser(User managerUser) {
        this.managerUser = managerUser;
    }

    public String getManagerDisplayName() {
        return managerDisplayName;
    }

    public void setManagerDisplayName(String managerDisplayName) {
        this.managerDisplayName = managerDisplayName;
    }

    public String getProvider() {
        return provider;
    }

    public void setProvider(String provider) {
        this.provider = provider;
    }

    public String getStatus() {
        return status;
    }

    public void setStatus(String status) {
        this.status = status;
    }

    public String getRoomName() {
        return roomName;
    }

    public void setRoomName(String roomName) {
        this.roomName = roomName;
    }

    public String getStageMessage() {
        return stageMessage;
    }

    public void setStageMessage(String stageMessage) {
        this.stageMessage = stageMessage;
    }

    public Instant getStartedAt() {
        return startedAt;
    }

    public void setStartedAt(Instant startedAt) {
        this.startedAt = startedAt;
    }

    public Instant getLiveAt() {
        return liveAt;
    }

    public void setLiveAt(Instant liveAt) {
        this.liveAt = liveAt;
    }

    public Instant getEndedAt() {
        return endedAt;
    }

    public void setEndedAt(Instant endedAt) {
        this.endedAt = endedAt;
    }
}
