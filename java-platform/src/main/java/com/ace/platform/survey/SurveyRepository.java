package com.ace.platform.survey;

import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

public interface SurveyRepository extends JpaRepository<Survey, Long> {
    List<Survey> findByOrganizationIdOrderByUpdatedAtDescCreatedAtDesc(Long organizationId);
    Optional<Survey> findByIdAndOrganizationId(Long id, Long organizationId);
    Optional<Survey> findByOrganizationIdAndSlug(Long organizationId, String slug);
    boolean existsByOrganizationIdAndSlug(Long organizationId, String slug);
    boolean existsByOrganizationIdAndSlugAndIdNot(Long organizationId, String slug, Long id);
}
