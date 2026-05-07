package com.ace.platform.lead;

import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

public interface LeadRepository extends JpaRepository<Lead, Long> {
    Optional<Lead> findByOrganizationIdAndSid(Long organizationId, String sid);
    List<Lead> findByOrganizationIdOrderByLastMessageAtDescCreatedAtDesc(Long organizationId);
    List<Lead> findByOrganizationIdAndTakeoverActiveTrueOrderByLastMessageAtDescCreatedAtDesc(Long organizationId);
    List<Lead> findByOrganizationIdOrderByLastMessageAtDescCreatedAtDesc(Long organizationId, Pageable pageable);
}
