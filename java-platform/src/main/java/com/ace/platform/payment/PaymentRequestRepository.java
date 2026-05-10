package com.ace.platform.payment;

import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

public interface PaymentRequestRepository extends JpaRepository<PaymentRequest, Long> {
    List<PaymentRequest> findByOrganizationIdOrderByCreatedAtDesc(Long organizationId, Pageable pageable);
    List<PaymentRequest> findByOrganizationIdAndSidOrderByCreatedAtDesc(Long organizationId, String sid, Pageable pageable);
    Optional<PaymentRequest> findByOrganizationIdAndId(Long organizationId, Long id);
    Optional<PaymentRequest> findByPublicToken(String publicToken);
}
