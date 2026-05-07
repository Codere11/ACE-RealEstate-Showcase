package com.ace.platform.publicsite;

import com.ace.platform.chat.PublicChatService;
import com.ace.platform.chat.TakeoverService;
import com.ace.platform.conversation.ConversationMessageRepository;
import com.ace.platform.conversation.ConversationService;
import com.ace.platform.events.LeadEventRepository;
import com.ace.platform.events.LeadEventService;
import com.ace.platform.lead.Lead;
import com.ace.platform.lead.LeadRepository;
import com.ace.platform.lead.LeadService;
import com.ace.platform.organization.Organization;
import com.ace.platform.organization.OrganizationRepository;
import com.ace.platform.survey.SurveyService;
import com.ace.platform.user.UserRepository;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;

import java.util.List;
import java.util.Optional;

import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
class PublicRoutingTests {

    private Lead leadFor(Organization organization, String sid) {
        return new Lead(organization, sid, "Visitor " + sid, "start");
    }

    private SurveyService.SurveyDefinition defaultSurvey() {
        return new SurveyService.SurveyDefinition(
            1L,
            "Property intake survey",
            "start",
            "Default public-facing survey for visitor qualification.",
            true,
            true,
            List.of(
                new SurveyService.QuestionDefinition(
                    1L,
                    1,
                    com.ace.platform.survey.SurveyQuestionType.SINGLE_CHOICE,
                    "What kind of property are you interested in?",
                    "",
                    "",
                    true,
                    List.of(
                        new SurveyService.QuestionOptionDefinition(1L, 1, "Buying a home", "Buying a home"),
                        new SurveyService.QuestionOptionDefinition(2L, 2, "Selling a property", "Selling a property")
                    )
                )
            )
        );
    }

    @Autowired
    private MockMvc mockMvc;

    @MockBean
    private OrganizationRepository organizationRepository;

    @MockBean
    private UserRepository userRepository;

    @MockBean
    private PasswordEncoder passwordEncoder;

    @MockBean
    private LeadRepository leadRepository;

    @MockBean
    private ConversationMessageRepository conversationMessageRepository;

    @MockBean
    private LeadEventRepository leadEventRepository;

    @MockBean
    private LeadService leadService;

    @MockBean
    private ConversationService conversationService;

    @MockBean
    private LeadEventService leadEventService;

    @MockBean
    private PublicChatService publicChatService;

    @MockBean
    private TakeoverService takeoverService;

    @MockBean
    private SurveyService surveyService;

    @Test
    void rootRouteLoads() throws Exception {
        mockMvc.perform(get("/"))
            .andExpect(status().isOk())
            .andExpect(content().string(org.hamcrest.Matchers.containsString("ACE Platform")));
    }

    @Test
    void demoRouteResolvesFromDatabase() throws Exception {
        Organization organization = new Organization("Demo Agency", "demo", true);
        when(organizationRepository.findBySlugAndActiveTrue("demo"))
            .thenReturn(Optional.of(organization));
        when(leadService.getOrCreateLead(organization, null, "start"))
            .thenReturn(leadFor(organization, "sid_demo"));
        when(surveyService.ensureDefaultSurveyDefinition(organization, "start"))
            .thenReturn(defaultSurvey());
        when(conversationService.getThread(org.mockito.ArgumentMatchers.any(Lead.class)))
            .thenReturn(List.of());

        mockMvc.perform(get("/demo"))
            .andExpect(status().isOk())
            .andExpect(content().string(org.hamcrest.Matchers.containsString("0% complete")))
            .andExpect(content().string(org.hamcrest.Matchers.containsString("Buying a home")));
    }

    @Test
    void tenantRouteResolvesFromDatabase() throws Exception {
        Organization organization = new Organization("Acme Realty", "acme", true);
        when(organizationRepository.findBySlugAndActiveTrue("acme"))
            .thenReturn(Optional.of(organization));
        when(leadService.getOrCreateLead(organization, null, "start"))
            .thenReturn(leadFor(organization, "sid_acme"));
        when(surveyService.ensureDefaultSurveyDefinition(organization, "start"))
            .thenReturn(defaultSurvey());
        when(conversationService.getThread(org.mockito.ArgumentMatchers.any(Lead.class)))
            .thenReturn(List.of());

        mockMvc.perform(get("/acme"))
            .andExpect(status().isOk())
            .andExpect(content().string(org.hamcrest.Matchers.containsString("0% complete")))
            .andExpect(content().string(org.hamcrest.Matchers.containsString("What kind of property are you interested in?")));
    }

    @Test
    void missingTenantReturnsNotFoundPage() throws Exception {
        when(organizationRepository.findBySlugAndActiveTrue("missing"))
            .thenReturn(Optional.empty());

        mockMvc.perform(get("/missing"))
            .andExpect(status().isNotFound())
            .andExpect(content().string(org.hamcrest.Matchers.containsString("Tenant not found")));
    }

    @Test
    void reservedPathIsNotHandledAsTenant() throws Exception {
        when(organizationRepository.findBySlugAndActiveTrue(anyString()))
            .thenReturn(Optional.empty());

        mockMvc.perform(get("/api"))
            .andExpect(status().isNotFound())
            .andExpect(content().string(org.hamcrest.Matchers.containsString("Reserved route")));
    }

    @Test
    void organizationDashboardRouteLoads() throws Exception {
        when(organizationRepository.findBySlugAndActiveTrue("demo"))
            .thenReturn(Optional.of(new Organization("Demo Agency", "demo", true)));

        mockMvc.perform(get("/demo/dashboard"))
            .andExpect(status().is3xxRedirection());
    }

    @Test
    void tenantSurveyRouteLoads() throws Exception {
        Organization organization = new Organization("Demo Agency", "demo", true);
        when(organizationRepository.findBySlugAndActiveTrue("demo"))
            .thenReturn(Optional.of(organization));
        when(leadService.getOrCreateLead(organization, null, "start"))
            .thenReturn(leadFor(organization, "sid_demo"));
        when(surveyService.ensureDefaultSurveyDefinition(organization, "start"))
            .thenReturn(defaultSurvey());
        when(conversationService.getThread(org.mockito.ArgumentMatchers.any(Lead.class)))
            .thenReturn(List.of());

        mockMvc.perform(get("/demo/survey/start"))
            .andExpect(status().isOk())
            .andExpect(content().string(org.hamcrest.Matchers.containsString("0% complete")))
            .andExpect(content().string(org.hamcrest.Matchers.containsString("Buying a home")));
    }
}
