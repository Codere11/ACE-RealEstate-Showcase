package com.ace.platform.qualifier;

import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

public interface QualifierRepository extends JpaRepository<Qualifier, Long> {

    List<Qualifier> findByOrganizationIdOrderByUpdatedAtDescCreatedAtDesc(Long organizationId);

    Optional<Qualifier> findByIdAndOrganizationId(Long id, Long organizationId);

    Optional<Qualifier> findByOrganizationIdAndStatus(Long organizationId, String status);

    boolean existsByOrganizationIdAndSlug(Long organizationId, String slug);

    boolean existsByOrganizationIdAndSlugAndIdNot(Long organizationId, String slug, Long id);

    boolean existsByOrganizationIdAndStatusAndIdNot(Long organizationId, String status, Long id);

    boolean existsByOrganizationIdAndStatus(Long organizationId, String status);
}
