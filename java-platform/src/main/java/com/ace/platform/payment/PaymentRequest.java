package com.ace.platform.payment;

import com.ace.platform.common.model.BaseEntity;
import com.ace.platform.organization.Organization;
import com.ace.platform.user.User;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

import java.time.Instant;
import java.util.Map;

@Entity
@Table(name = "payment_requests")
public class PaymentRequest extends BaseEntity {

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "organization_id", nullable = false)
    private Organization organization;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "created_by_user_id")
    private User createdByUser;

    @Column(name = "sid", nullable = false, length = 64)
    private String sid;

    @Column(name = "provider", nullable = false, length = 32)
    private String provider = "mock";

    @Column(name = "provider_payment_id", length = 160)
    private String providerPaymentId;

    @Column(name = "provider_session_id", length = 160)
    private String providerSessionId;

    @Column(name = "public_token", nullable = false, unique = true, length = 64)
    private String publicToken;

    @Column(name = "amount_cents", nullable = false)
    private int amountCents;

    @Column(name = "currency", nullable = false, length = 8)
    private String currency = "EUR";

    @Column(name = "purpose", nullable = false, length = 160)
    private String purpose = "Payment request";

    @Column(name = "note", nullable = false, columnDefinition = "text")
    private String note = "";

    @Column(name = "status", nullable = false, length = 16)
    private String status = "sent";

    @Column(name = "payment_url", nullable = false, columnDefinition = "text")
    private String paymentUrl;

    @Column(name = "expires_at")
    private Instant expiresAt;

    @Column(name = "paid_at")
    private Instant paidAt;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "provider_payload", columnDefinition = "jsonb")
    private Map<String, Object> providerPayload;

    protected PaymentRequest() {
    }

    public PaymentRequest(Organization organization, User createdByUser, String sid, String publicToken, int amountCents, String currency, String purpose, String note) {
        this.organization = organization;
        this.createdByUser = createdByUser;
        this.sid = sid;
        this.publicToken = publicToken;
        this.amountCents = amountCents;
        this.currency = currency;
        this.purpose = purpose;
        this.note = note;
        this.paymentUrl = "";
    }

    public Organization getOrganization() {
        return organization;
    }

    public void setOrganization(Organization organization) {
        this.organization = organization;
    }

    public User getCreatedByUser() {
        return createdByUser;
    }

    public void setCreatedByUser(User createdByUser) {
        this.createdByUser = createdByUser;
    }

    public String getSid() {
        return sid;
    }

    public void setSid(String sid) {
        this.sid = sid;
    }

    public String getProvider() {
        return provider;
    }

    public void setProvider(String provider) {
        this.provider = provider;
    }

    public String getProviderPaymentId() {
        return providerPaymentId;
    }

    public void setProviderPaymentId(String providerPaymentId) {
        this.providerPaymentId = providerPaymentId;
    }

    public String getProviderSessionId() {
        return providerSessionId;
    }

    public void setProviderSessionId(String providerSessionId) {
        this.providerSessionId = providerSessionId;
    }

    public String getPublicToken() {
        return publicToken;
    }

    public void setPublicToken(String publicToken) {
        this.publicToken = publicToken;
    }

    public int getAmountCents() {
        return amountCents;
    }

    public void setAmountCents(int amountCents) {
        this.amountCents = amountCents;
    }

    public String getCurrency() {
        return currency;
    }

    public void setCurrency(String currency) {
        this.currency = currency;
    }

    public String getPurpose() {
        return purpose;
    }

    public void setPurpose(String purpose) {
        this.purpose = purpose;
    }

    public String getNote() {
        return note;
    }

    public void setNote(String note) {
        this.note = note;
    }

    public String getStatus() {
        return status;
    }

    public void setStatus(String status) {
        this.status = status;
    }

    public String getPaymentUrl() {
        return paymentUrl;
    }

    public void setPaymentUrl(String paymentUrl) {
        this.paymentUrl = paymentUrl;
    }

    public Instant getExpiresAt() {
        return expiresAt;
    }

    public void setExpiresAt(Instant expiresAt) {
        this.expiresAt = expiresAt;
    }

    public Instant getPaidAt() {
        return paidAt;
    }

    public void setPaidAt(Instant paidAt) {
        this.paidAt = paidAt;
    }

    public Map<String, Object> getProviderPayload() {
        return providerPayload;
    }

    public void setProviderPayload(Map<String, Object> providerPayload) {
        this.providerPayload = providerPayload;
    }
}
