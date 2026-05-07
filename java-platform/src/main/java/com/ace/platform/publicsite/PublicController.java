package com.ace.platform.publicsite;

import com.ace.platform.lead.Lead;
import com.ace.platform.lead.LeadService;
import com.ace.platform.organization.Organization;
import com.ace.platform.survey.SurveyService;
import com.ace.platform.tenant.TenantRouteService;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestParam;

@Controller
public class PublicController {

    private static final String DEFAULT_SURVEY_SLUG = "start";

    private final TenantRouteService tenantRouteService;
    private final LeadService leadService;
    private final SurveyService surveyService;

    public PublicController(
        TenantRouteService tenantRouteService,
        LeadService leadService,
        SurveyService surveyService
    ) {
        this.tenantRouteService = tenantRouteService;
        this.leadService = leadService;
        this.surveyService = surveyService;
    }

    @GetMapping("/")
    public String root(Model model) {
        model.addAttribute("message", "ACE Spring Boot rewrite shell is running.");
        model.addAttribute("pageMode", "root");
        model.addAttribute("pageTitle", "ACE Platform");
        model.addAttribute("routeLabel", "/");
        return "public/home";
    }

    @GetMapping("/demo")
    public String demo(
        @RequestParam(name = "sid", required = false) String sid,
        Model model,
        HttpServletResponse response
    ) {
        return tenantRouteService.findActiveOrganizationBySlug("demo")
            .map(org -> renderTenantSurvey(model, org, DEFAULT_SURVEY_SLUG, sid))
            .orElseGet(() -> renderNotFound(model, response, "Tenant not found", "The demo route exists conceptually, but no active demo organization is available.", "demo"));
    }

    @GetMapping("/{tenantSlug:[a-zA-Z0-9][a-zA-Z0-9-]*}")
    public String tenant(
        @PathVariable String tenantSlug,
        @RequestParam(name = "sid", required = false) String sid,
        Model model,
        HttpServletResponse response
    ) {
        if (tenantRouteService.isReservedPathSegment(tenantSlug)) {
            return renderNotFound(model, response, "Reserved route", "This path is reserved by the platform and is not interpreted as a tenant slug.", tenantSlug);
        }

        return tenantRouteService.findActiveOrganizationBySlug(tenantSlug)
            .map(org -> renderTenantSurvey(model, org, DEFAULT_SURVEY_SLUG, sid))
            .orElseGet(() -> renderNotFound(model, response, "Tenant not found", "No active organization was found for this tenant slug.", tenantSlug));
    }

    @GetMapping("/{tenantSlug:[a-zA-Z0-9][a-zA-Z0-9-]*}/survey/{surveySlug:[a-zA-Z0-9][a-zA-Z0-9-]*}")
    public String tenantSurvey(
        @PathVariable String tenantSlug,
        @PathVariable String surveySlug,
        @RequestParam(name = "sid", required = false) String sid,
        Model model,
        HttpServletResponse response
    ) {
        if (tenantRouteService.isReservedPathSegment(tenantSlug)) {
            return renderNotFound(model, response, "Reserved route", "This path is reserved by the platform and is not interpreted as a tenant slug.", tenantSlug);
        }

        return tenantRouteService.findActiveOrganizationBySlug(tenantSlug)
            .map(org -> renderTenantSurvey(model, org, surveySlug, sid))
            .orElseGet(() -> renderNotFound(model, response, "Tenant not found", "No active organization was found for this survey route.", tenantSlug));
    }

    private String renderTenantSurvey(Model model, Organization organization, String surveySlug, String sid) {
        SurveyService.SurveyDefinition surveyDefinition = surveyService.ensureDefaultSurveyDefinition(organization, surveySlug);
        Lead lead = leadService.getOrCreateLead(organization, sid, surveyDefinition.slug());
        model.addAttribute("organization", organization);
        model.addAttribute("surveySlug", surveyDefinition.slug());
        model.addAttribute("isDefaultSurvey", DEFAULT_SURVEY_SLUG.equalsIgnoreCase(surveyDefinition.slug()));
        model.addAttribute("sid", lead.getSid());
        model.addAttribute("lead", lead);
        model.addAttribute("surveyDefinition", surveyDefinition);
        model.addAttribute("progressPercent", Math.max(0, lead.getSurveyProgress()));
        return "public/survey";
    }

    private String renderNotFound(Model model, HttpServletResponse response, String title, String message, String pathSegment) {
        response.setStatus(HttpServletResponse.SC_NOT_FOUND);
        model.addAttribute("title", title);
        model.addAttribute("message", message);
        model.addAttribute("pathSegment", pathSegment);
        return "public/not-found";
    }
}
