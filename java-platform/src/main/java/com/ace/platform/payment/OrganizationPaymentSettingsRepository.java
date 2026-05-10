package com.ace.platform.payment;

import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;

public interface OrganizationPaymentSettingsRepository extends JpaRepository<OrganizationPaymentSettings, Long> {
    Optional<OrganizationPaymentSettings> findByOrganizationId(Long organizationId);
    Optional<OrganizationPaymentSettings> findByStripeOauthState(String stripeOauthState);
    Optional<OrganizationPaymentSettings> findByStripeAccountId(String stripeAccountId);
}
