package com.ace.platform.payment;

import com.ace.platform.common.model.BaseEntity;
import com.ace.platform.organization.Organization;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;

import java.time.Instant;

@Entity
@Table(name = "organization_payment_settings")
public class OrganizationPaymentSettings extends BaseEntity {

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "organization_id", nullable = false, unique = true)
    private Organization organization;

    @Column(name = "provider", nullable = false, length = 32)
    private String provider = "stripe";

    @Column(name = "mode", nullable = false, length = 32)
    private String mode = "stripe_connect_standard";

    @Column(name = "payments_enabled", nullable = false)
    private boolean paymentsEnabled;

    @Column(name = "default_currency", nullable = false, length = 8)
    private String defaultCurrency = "EUR";

    @Column(name = "stripe_account_id", length = 64)
    private String stripeAccountId;

    @Column(name = "stripe_connect_status", nullable = false, length = 24)
    private String stripeConnectStatus = "not_connected";

    @Column(name = "stripe_onboarding_complete", nullable = false)
    private boolean stripeOnboardingComplete;

    @Column(name = "stripe_details_submitted", nullable = false)
    private boolean stripeDetailsSubmitted;

    @Column(name = "stripe_charges_enabled", nullable = false)
    private boolean stripeChargesEnabled;

    @Column(name = "stripe_payouts_enabled", nullable = false)
    private boolean stripePayoutsEnabled;

    @Column(name = "stripe_access_token", columnDefinition = "text")
    private String stripeAccessToken;

    @Column(name = "stripe_refresh_token", columnDefinition = "text")
    private String stripeRefreshToken;

    @Column(name = "stripe_publishable_key", length = 255)
    private String stripePublishableKey;

    @Column(name = "stripe_scope", length = 64)
    private String stripeScope;

    @Column(name = "stripe_livemode", nullable = false)
    private boolean stripeLivemode;

    @Column(name = "stripe_oauth_state", length = 160)
    private String stripeOauthState;

    @Column(name = "stripe_last_error", columnDefinition = "text")
    private String stripeLastError;

    @Column(name = "last_synced_at")
    private Instant lastSyncedAt;

    protected OrganizationPaymentSettings() {
    }

    public OrganizationPaymentSettings(Organization organization) {
        this.organization = organization;
    }

    public Organization getOrganization() {
        return organization;
    }

    public void setOrganization(Organization organization) {
        this.organization = organization;
    }

    public String getProvider() {
        return provider;
    }

    public void setProvider(String provider) {
        this.provider = provider;
    }

    public String getMode() {
        return mode;
    }

    public void setMode(String mode) {
        this.mode = mode;
    }

    public boolean isPaymentsEnabled() {
        return paymentsEnabled;
    }

    public void setPaymentsEnabled(boolean paymentsEnabled) {
        this.paymentsEnabled = paymentsEnabled;
    }

    public String getDefaultCurrency() {
        return defaultCurrency;
    }

    public void setDefaultCurrency(String defaultCurrency) {
        this.defaultCurrency = defaultCurrency;
    }

    public String getStripeAccountId() {
        return stripeAccountId;
    }

    public void setStripeAccountId(String stripeAccountId) {
        this.stripeAccountId = stripeAccountId;
    }

    public String getStripeConnectStatus() {
        return stripeConnectStatus;
    }

    public void setStripeConnectStatus(String stripeConnectStatus) {
        this.stripeConnectStatus = stripeConnectStatus;
    }

    public boolean isStripeOnboardingComplete() {
        return stripeOnboardingComplete;
    }

    public void setStripeOnboardingComplete(boolean stripeOnboardingComplete) {
        this.stripeOnboardingComplete = stripeOnboardingComplete;
    }

    public boolean isStripeDetailsSubmitted() {
        return stripeDetailsSubmitted;
    }

    public void setStripeDetailsSubmitted(boolean stripeDetailsSubmitted) {
        this.stripeDetailsSubmitted = stripeDetailsSubmitted;
    }

    public boolean isStripeChargesEnabled() {
        return stripeChargesEnabled;
    }

    public void setStripeChargesEnabled(boolean stripeChargesEnabled) {
        this.stripeChargesEnabled = stripeChargesEnabled;
    }

    public boolean isStripePayoutsEnabled() {
        return stripePayoutsEnabled;
    }

    public void setStripePayoutsEnabled(boolean stripePayoutsEnabled) {
        this.stripePayoutsEnabled = stripePayoutsEnabled;
    }

    public String getStripeAccessToken() {
        return stripeAccessToken;
    }

    public void setStripeAccessToken(String stripeAccessToken) {
        this.stripeAccessToken = stripeAccessToken;
    }

    public String getStripeRefreshToken() {
        return stripeRefreshToken;
    }

    public void setStripeRefreshToken(String stripeRefreshToken) {
        this.stripeRefreshToken = stripeRefreshToken;
    }

    public String getStripePublishableKey() {
        return stripePublishableKey;
    }

    public void setStripePublishableKey(String stripePublishableKey) {
        this.stripePublishableKey = stripePublishableKey;
    }

    public String getStripeScope() {
        return stripeScope;
    }

    public void setStripeScope(String stripeScope) {
        this.stripeScope = stripeScope;
    }

    public boolean isStripeLivemode() {
        return stripeLivemode;
    }

    public void setStripeLivemode(boolean stripeLivemode) {
        this.stripeLivemode = stripeLivemode;
    }

    public String getStripeOauthState() {
        return stripeOauthState;
    }

    public void setStripeOauthState(String stripeOauthState) {
        this.stripeOauthState = stripeOauthState;
    }

    public String getStripeLastError() {
        return stripeLastError;
    }

    public void setStripeLastError(String stripeLastError) {
        this.stripeLastError = stripeLastError;
    }

    public Instant getLastSyncedAt() {
        return lastSyncedAt;
    }

    public void setLastSyncedAt(Instant lastSyncedAt) {
        this.lastSyncedAt = lastSyncedAt;
    }
}
