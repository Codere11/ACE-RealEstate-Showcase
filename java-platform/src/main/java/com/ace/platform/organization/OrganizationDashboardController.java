package com.ace.platform.organization;

import com.ace.platform.tenant.TenantRouteService;
import com.ace.platform.user.User;
import com.ace.platform.user.UserRepository;
import com.ace.platform.user.UserRole;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestParam;

import java.security.Principal;

@Controller
public class OrganizationDashboardController {

    private final TenantRouteService tenantRouteService;
    private final UserRepository userRepository;

    public OrganizationDashboardController(TenantRouteService tenantRouteService, UserRepository userRepository) {
        this.tenantRouteService = tenantRouteService;
        this.userRepository = userRepository;
    }

    @GetMapping("/{tenantSlug:[a-zA-Z0-9][a-zA-Z0-9-]*}/dashboard")
    public String dashboard(
        @PathVariable String tenantSlug,
        @RequestParam(name = "tab", defaultValue = "leads") String tab,
        Model model,
        Principal principal,
        HttpServletResponse response
    ) {
        if (tenantRouteService.isReservedPathSegment(tenantSlug)) {
            response.setStatus(HttpServletResponse.SC_NOT_FOUND);
            model.addAttribute("title", "Reserved route");
            model.addAttribute("message", "This path is reserved by the platform and is not interpreted as an organization slug.");
            model.addAttribute("pathSegment", tenantSlug);
            return "public/not-found";
        }

        Organization organization = tenantRouteService.findActiveOrganizationBySlug(tenantSlug).orElse(null);
        if (organization == null) {
            response.setStatus(HttpServletResponse.SC_NOT_FOUND);
            model.addAttribute("title", "Organization not found");
            model.addAttribute("message", "No active organization was found for this dashboard route.");
            model.addAttribute("pathSegment", tenantSlug);
            return "public/not-found";
        }

        User currentUser = principal != null ? userRepository.findByUsername(principal.getName()).orElse(null) : null;
        if (currentUser == null) {
            response.setStatus(HttpServletResponse.SC_FORBIDDEN);
            model.addAttribute("title", "Access denied");
            model.addAttribute("message", "You must be logged in to access this organization dashboard.");
            model.addAttribute("pathSegment", tenantSlug);
            return "public/not-found";
        }

        boolean isPlatformAdmin = currentUser.getRole() == UserRole.PLATFORM_ADMIN;
        boolean belongsToOrganization = currentUser.getOrganization() != null
            && currentUser.getOrganization().getSlug() != null
            && currentUser.getOrganization().getSlug().equalsIgnoreCase(tenantSlug);

        if (!isPlatformAdmin && !belongsToOrganization) {
            response.setStatus(HttpServletResponse.SC_FORBIDDEN);
            model.addAttribute("title", "Access denied");
            model.addAttribute("message", "This user does not have access to the requested organization dashboard.");
            model.addAttribute("pathSegment", tenantSlug);
            return "public/not-found";
        }

        model.addAttribute("organization", organization);
        model.addAttribute("activeTab", normalizeTab(tab));
        model.addAttribute("viewer", principal.getName());
        return "organization/dashboard";
    }

    private String normalizeTab(String tab) {
        if (tab == null || tab.isBlank()) {
            return "leads";
        }
        return switch (tab.trim().toLowerCase()) {
            case "surveys" -> "surveys";
            case "qualifier" -> "qualifier";
            case "payments" -> "payments";
            default -> "leads";
        };
    }
}
