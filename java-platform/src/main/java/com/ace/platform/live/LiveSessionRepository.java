package com.ace.platform.live;

import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;

public interface LiveSessionRepository extends JpaRepository<LiveSession, Long> {
    Optional<LiveSession> findFirstByOrganizationIdAndSidOrderByCreatedAtDescIdDesc(Long organizationId, String sid);
    Optional<LiveSession> findByIdAndOrganizationId(Long id, Long organizationId);
}
