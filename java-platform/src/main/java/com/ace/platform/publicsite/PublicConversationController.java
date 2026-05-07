package com.ace.platform.publicsite;

import com.ace.platform.chat.PublicChatService;
import com.ace.platform.conversation.ConversationService;
import com.ace.platform.lead.Lead;
import com.ace.platform.lead.LeadService;
import com.ace.platform.organization.Organization;
import com.ace.platform.organization.OrganizationRepository;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.stereotype.Controller;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.servlet.mvc.support.RedirectAttributes;

@Controller
public class PublicConversationController {

    private final OrganizationRepository organizationRepository;
    private final LeadService leadService;
    private final PublicChatService publicChatService;

    public PublicConversationController(
        OrganizationRepository organizationRepository,
        LeadService leadService,
        PublicChatService publicChatService
    ) {
        this.organizationRepository = organizationRepository;
        this.leadService = leadService;
        this.publicChatService = publicChatService;
    }

    @PostMapping("/{tenantSlug:[a-zA-Z0-9][a-zA-Z0-9-]*}/survey/{surveySlug:[a-zA-Z0-9][a-zA-Z0-9-]*}/send")
    public String send(
        @PathVariable String tenantSlug,
        @PathVariable String surveySlug,
        @RequestParam(required = false) String sid,
        @RequestParam String message,
        RedirectAttributes redirectAttributes
    ) {
        Organization organization = organizationRepository.findBySlugAndActiveTrue(tenantSlug).orElse(null);
        if (organization == null) {
            redirectAttributes.addFlashAttribute("errorMessage", "Tenant not found.");
            return "redirect:/" + tenantSlug + "/survey/" + surveySlug;
        }

        PublicChatService.ChatResult result = publicChatService.handleVisitorMessage(organization, sid, surveySlug, message);
        if (result.storyComplete()) {
            redirectAttributes.addFlashAttribute("successMessage", "Lead captured. A team member can continue from the dashboard.");
        }
        return "redirect:/" + tenantSlug + "/survey/" + surveySlug + "?sid=" + result.sid();
    }
}
