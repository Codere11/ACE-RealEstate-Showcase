package com.ace.platform.publicsite;

import com.ace.platform.organization.OrganizationRepository;
import com.ace.platform.tenant.TenantRouteService;
import org.springframework.core.io.ClassPathResource;
import org.springframework.core.io.Resource;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Controller;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.ResponseBody;

import java.util.Map;

/**
 * Public controller — serves the Angular SPA for visitor routes.
 * When the Angular SPA static files are available (classpath:static/index.html),
 * visitor routes are served by the SPA. Otherwise, returns JSON status.
 */
@Controller
public class PublicController {

    private final TenantRouteService tenantRouteService;
    private final OrganizationRepository organizationRepository;
    private final boolean spaAvailable;

    public PublicController(
        TenantRouteService tenantRouteService,
        OrganizationRepository organizationRepository
    ) {
        this.tenantRouteService = tenantRouteService;
        this.organizationRepository = organizationRepository;
        this.spaAvailable = new ClassPathResource("static/index.html").exists();
    }

    @GetMapping({"/", "/demo", "/admin", "/admin/dashboard", "/{tenantSlug:[a-zA-Z0-9][a-zA-Z0-9-]*}", "/{tenantSlug:[a-zA-Z0-9][a-zA-Z0-9-]*}/dashboard"})
    public String visitorRoutes(@PathVariable(required = false) String tenantSlug) {
        if (spaAvailable) {
            return "forward:/index.html";
        }
        String org = tenantSlug != null ? tenantSlug : "demo";
        return "redirect:http://localhost:4200/?org=" + org;
    }

    @GetMapping(value = "/api/public/organizations/{orgSlug}/status", produces = MediaType.APPLICATION_JSON_VALUE)
    @ResponseBody
    public Map<String, Object> status(@PathVariable String orgSlug) {
        return organizationRepository.findBySlugAndActiveTrue(orgSlug)
            .map(org -> Map.<String, Object>of(
                "status", "ok",
                "organization", org.getName(),
                "slug", org.getSlug()
            ))
            .orElse(Map.of(
                "status", "not_found",
                "slug", orgSlug
            ));
    }
}
