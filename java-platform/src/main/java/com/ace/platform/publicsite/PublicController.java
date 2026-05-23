package com.ace.platform.publicsite;

import com.ace.platform.organization.OrganizationRepository;
import com.ace.platform.tenant.TenantRouteService;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Controller;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.ResponseBody;

import java.util.Map;

/**
 * Minimal public controller — the visitor-facing UI is served by the Angular SPA.
 * These endpoints now return JSON status for debugging / health checks.
 */
@Controller
public class PublicController {

    private final TenantRouteService tenantRouteService;
    private final OrganizationRepository organizationRepository;

    public PublicController(
        TenantRouteService tenantRouteService,
        OrganizationRepository organizationRepository
    ) {
        this.tenantRouteService = tenantRouteService;
        this.organizationRepository = organizationRepository;
    }

    @GetMapping(value = "/", produces = MediaType.APPLICATION_JSON_VALUE)
    @ResponseBody
    public Map<String, Object> root() {
        return Map.of(
            "status", "ok",
            "message", "ACE Reception Services — visitor UI is served by the Angular SPA"
        );
    }

    @GetMapping(value = "/demo", produces = MediaType.APPLICATION_JSON_VALUE)
    @ResponseBody
    public Map<String, Object> demo() {
        return organizationRepository.findBySlugAndActiveTrue("demo")
            .map(org -> Map.<String, Object>of(
                "status", "ok",
                "organization", org.getName(),
                "slug", org.getSlug(),
                "message", "Visitor UI is served by the Angular SPA"
            ))
            .orElse(Map.of(
                "status", "not_found",
                "message", "No active demo organization"
            ));
    }

    @GetMapping(value = "/{tenantSlug:[a-zA-Z0-9][a-zA-Z0-9-]*}", produces = MediaType.APPLICATION_JSON_VALUE)
    @ResponseBody
    public Map<String, Object> tenant(@PathVariable String tenantSlug) {
        if (tenantRouteService.isReservedPathSegment(tenantSlug)) {
            return Map.of("status", "reserved", "slug", tenantSlug);
        }
        return organizationRepository.findBySlugAndActiveTrue(tenantSlug)
            .map(org -> Map.<String, Object>of(
                "status", "ok",
                "organization", org.getName(),
                "slug", org.getSlug()
            ))
            .orElse(Map.of(
                "status", "not_found",
                "slug", tenantSlug
            ));
    }
}
