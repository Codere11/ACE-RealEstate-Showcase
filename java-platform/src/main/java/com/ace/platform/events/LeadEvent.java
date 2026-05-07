package com.ace.platform.events;

import com.ace.platform.common.model.BaseEntity;
import com.ace.platform.organization.Organization;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;

@Entity
@Table(name = "lead_events")
public class LeadEvent extends BaseEntity {

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "organization_id", nullable = false)
    private Organization organization;

    @Column(name = "sid", nullable = false, length = 120)
    private String sid;

    @Column(name = "event_type", nullable = false, length = 120)
    private String eventType;

    @Column(name = "payload_json", nullable = false, columnDefinition = "TEXT")
    private String payloadJson;

    protected LeadEvent() {
    }

    public LeadEvent(Organization organization, String sid, String eventType, String payloadJson) {
        this.organization = organization;
        this.sid = sid;
        this.eventType = eventType;
        this.payloadJson = payloadJson;
    }

    public Organization getOrganization() {
        return organization;
    }

    public String getSid() {
        return sid;
    }

    public String getEventType() {
        return eventType;
    }

    public String getPayloadJson() {
        return payloadJson;
    }
}
