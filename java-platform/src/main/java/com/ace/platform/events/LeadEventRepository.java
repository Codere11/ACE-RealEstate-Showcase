package com.ace.platform.events;

import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface LeadEventRepository extends JpaRepository<LeadEvent, Long> {
    List<LeadEvent> findByOrganizationIdAndSidAndIdGreaterThanOrderByIdAsc(Long organizationId, String sid, Long id, Pageable pageable);
    List<LeadEvent> findByOrganizationIdAndIdGreaterThanOrderByIdAsc(Long organizationId, Long id, Pageable pageable);
}
