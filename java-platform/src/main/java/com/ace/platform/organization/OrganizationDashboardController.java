package com.ace.platform.organization;

import com.ace.platform.chat.TakeoverService;
import com.ace.platform.conversation.ConversationService;
import com.ace.platform.lead.Lead;
import com.ace.platform.lead.LeadService;
import com.ace.platform.survey.Survey;
import com.ace.platform.survey.SurveyService;
import com.ace.platform.tenant.TenantRouteService;
import com.ace.platform.user.User;
import com.ace.platform.user.UserRepository;
import com.ace.platform.user.UserRole;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.servlet.mvc.support.RedirectAttributes;

import java.security.Principal;
import java.util.List;

@Controller
public class OrganizationDashboardController {

    private final TenantRouteService tenantRouteService;
    private final UserRepository userRepository;
    private final LeadService leadService;
    private final ConversationService conversationService;
    private final TakeoverService takeoverService;
    private final SurveyService surveyService;

    public OrganizationDashboardController(
        TenantRouteService tenantRouteService,
        UserRepository userRepository,
        LeadService leadService,
        ConversationService conversationService,
        TakeoverService takeoverService,
        SurveyService surveyService
    ) {
        this.tenantRouteService = tenantRouteService;
        this.userRepository = userRepository;
        this.leadService = leadService;
        this.conversationService = conversationService;
        this.takeoverService = takeoverService;
        this.surveyService = surveyService;
    }

    @GetMapping("/{tenantSlug:[a-zA-Z0-9][a-zA-Z0-9-]*}/dashboard")
    public String dashboard(
        @PathVariable String tenantSlug,
        @RequestParam(name = "tab", defaultValue = "leads") String tab,
        @RequestParam(name = "sid", required = false) String sid,
        @RequestParam(name = "surveyId", required = false) Long surveyId,
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

        String activeTab = normalizeTab(tab);
        Long effectiveSurveyId = surveyId;
        if ("surveys".equals(activeTab)) {
            Survey currentSurvey = surveyService.ensureDefaultSurvey(organization);
            if (effectiveSurveyId == null) {
                effectiveSurveyId = currentSurvey.getId();
            }
        }

        model.addAttribute("organization", organization);
        model.addAttribute("organizationId", organization.getId());
        model.addAttribute("activeTab", activeTab);
        model.addAttribute("viewer", principal.getName());
        model.addAttribute("orgUserCount", userRepository.countByOrganizationId(organization.getId()));
        model.addAttribute("selectedLeadSid", sid);
        model.addAttribute("selectedSurveyId", effectiveSurveyId);
        return "organization/dashboard";
    }

    @PostMapping("/{tenantSlug:[a-zA-Z0-9][a-zA-Z0-9-]*}/dashboard/takeover/send")
    public String sendTakeoverMessage(
        @PathVariable String tenantSlug,
        @RequestParam String sid,
        @RequestParam String text,
        Principal principal,
        RedirectAttributes redirectAttributes
    ) {
        User currentUser = resolveAuthorizedUser(tenantSlug, principal);
        if (currentUser == null) {
            redirectAttributes.addFlashAttribute("errorMessage", "You do not have access to this organization.");
            return "redirect:/" + tenantSlug + "/dashboard?tab=leads";
        }

        Lead lead = leadService.findByOrganizationAndSid(currentUser.getOrganization() != null ? currentUser.getOrganization().getId() : tenantRouteService.findActiveOrganizationBySlug(tenantSlug).map(Organization::getId).orElse(-1L), sid).orElse(null);
        if (lead == null && currentUser.getRole() == UserRole.PLATFORM_ADMIN) {
            Organization organization = tenantRouteService.findActiveOrganizationBySlug(tenantSlug).orElse(null);
            if (organization != null) {
                lead = leadService.findByOrganizationAndSid(organization.getId(), sid).orElse(null);
            }
        }
        if (lead == null) {
            redirectAttributes.addFlashAttribute("errorMessage", "Lead not found.");
            return "redirect:/" + tenantSlug + "/dashboard?tab=leads";
        }

        takeoverService.startTakeover(lead, currentUser, text);
        redirectAttributes.addFlashAttribute("successMessage", "Takeover message sent to " + lead.getDisplayName());
        return "redirect:/" + tenantSlug + "/dashboard?tab=leads&sid=" + sid;
    }

    @PostMapping("/{tenantSlug:[a-zA-Z0-9][a-zA-Z0-9-]*}/dashboard/takeover/end")
    public String endTakeover(
        @PathVariable String tenantSlug,
        @RequestParam String sid,
        Principal principal,
        RedirectAttributes redirectAttributes
    ) {
        User currentUser = resolveAuthorizedUser(tenantSlug, principal);
        if (currentUser == null) {
            redirectAttributes.addFlashAttribute("errorMessage", "You do not have access to this organization.");
            return "redirect:/" + tenantSlug + "/dashboard?tab=leads";
        }

        Organization organization = tenantRouteService.findActiveOrganizationBySlug(tenantSlug).orElse(null);
        Lead lead = organization != null ? leadService.findByOrganizationAndSid(organization.getId(), sid).orElse(null) : null;
        if (lead == null) {
            redirectAttributes.addFlashAttribute("errorMessage", "Lead not found.");
            return "redirect:/" + tenantSlug + "/dashboard?tab=leads";
        }

        takeoverService.endTakeover(lead);
        redirectAttributes.addFlashAttribute("successMessage", "Takeover ended for " + lead.getDisplayName());
        return "redirect:/" + tenantSlug + "/dashboard?tab=leads&sid=" + sid;
    }

    private User resolveAuthorizedUser(String tenantSlug, Principal principal) {
        if (principal == null) {
            return null;
        }
        User currentUser = userRepository.findByUsername(principal.getName()).orElse(null);
        if (currentUser == null) {
            return null;
        }
        if (currentUser.getRole() == UserRole.PLATFORM_ADMIN) {
            return currentUser;
        }
        if (currentUser.getOrganization() == null || currentUser.getOrganization().getSlug() == null) {
            return null;
        }
        return currentUser.getOrganization().getSlug().equalsIgnoreCase(tenantSlug) ? currentUser : null;
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
