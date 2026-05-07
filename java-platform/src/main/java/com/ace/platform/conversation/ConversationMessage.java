package com.ace.platform.conversation;

import com.ace.platform.common.model.BaseEntity;
import com.ace.platform.lead.Lead;
import com.ace.platform.organization.Organization;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.FetchType;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;

@Entity
@Table(name = "conversation_messages")
public class ConversationMessage extends BaseEntity {

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "organization_id", nullable = false)
    private Organization organization;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "lead_id", nullable = false)
    private Lead lead;

    @Enumerated(EnumType.STRING)
    @Column(name = "role", nullable = false, length = 50)
    private ConversationRole role;

    @Column(name = "text", nullable = false, columnDefinition = "TEXT")
    private String text;

    protected ConversationMessage() {
    }

    public ConversationMessage(Organization organization, Lead lead, ConversationRole role, String text) {
        this.organization = organization;
        this.lead = lead;
        this.role = role;
        this.text = text;
    }

    public Organization getOrganization() {
        return organization;
    }

    public Lead getLead() {
        return lead;
    }

    public ConversationRole getRole() {
        return role;
    }

    public void setRole(ConversationRole role) {
        this.role = role;
    }

    public String getText() {
        return text;
    }

    public void setText(String text) {
        this.text = text;
    }
}
