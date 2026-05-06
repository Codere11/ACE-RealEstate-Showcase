package com.ace.platform.tenant;

import com.ace.platform.organization.Organization;
import com.ace.platform.organization.OrganizationRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.Optional;
import java.util.Set;

@Service
public class TenantRouteService {

    private static final Set<String> RESERVED_PATH_SEGMENTS = Set.of(
        "admin",
        "login",
        "logout",
        "api",
        "actuator",
        "error",
        "favicon.ico",
        "robots.txt",
        "assets",
        "static",
        "css",
        "js",
        "images",
        "webjars"
    );

    private final OrganizationRepository organizationRepository;

    public TenantRouteService(OrganizationRepository organizationRepository) {
        this.organizationRepository = organizationRepository;
    }

    public boolean isReservedPathSegment(String segment) {
        return segment != null && RESERVED_PATH_SEGMENTS.contains(segment.toLowerCase());
    }

    @Transactional(readOnly = true)
    public Optional<Organization> findActiveOrganizationBySlug(String slug) {
        return organizationRepository.findBySlugAndActiveTrue(slug);
    }
}
