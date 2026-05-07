package com.ace.platform.security;

import com.ace.platform.chat.PublicChatService;
import com.ace.platform.chat.TakeoverService;
import com.ace.platform.conversation.ConversationMessageRepository;
import com.ace.platform.conversation.ConversationService;
import com.ace.platform.events.LeadEventRepository;
import com.ace.platform.events.LeadEventService;
import com.ace.platform.lead.LeadRepository;
import com.ace.platform.lead.LeadService;
import com.ace.platform.organization.Organization;
import com.ace.platform.organization.OrganizationRepository;
import com.ace.platform.survey.SurveyService;
import com.ace.platform.user.User;
import com.ace.platform.user.UserRepository;
import com.ace.platform.user.UserRole;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.test.context.support.WithMockUser;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;

import java.util.List;
import java.util.Optional;

import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.redirectedUrl;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
class AccessControlTests {

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
    @WithMockUser(username = "orgadmin", roles = "ORG_ADMIN")
    void orgAdminCannotOpenPlatformAdminDashboard() throws Exception {
        mockMvc.perform(get("/admin/dashboard"))
            .andExpect(status().isForbidden());
    }

    @Test
    @WithMockUser(username = "orgadmin", roles = "ORG_ADMIN")
    void orgAdminCanOpenOwnOrganizationDashboard() throws Exception {
        Organization organization = new Organization("Demo Agency", "demo", true);
        User user = new User(organization, "orgadmin", "orgadmin@demo.local", "hash", "pass", UserRole.ORG_ADMIN, true);

        when(organizationRepository.findBySlugAndActiveTrue("demo"))
            .thenReturn(Optional.of(organization));
        when(userRepository.findByUsername("orgadmin"))
            .thenReturn(Optional.of(user));
        when(userRepository.countByOrganizationId(anyLong())).thenReturn(1L);
        when(leadService.listForOrganization(anyLong())).thenReturn(List.of());

        mockMvc.perform(get("/demo/dashboard"))
            .andExpect(status().isOk())
            .andExpect(content().string(org.hamcrest.Matchers.containsString("ACE e-Counter Intelligence")));
    }

    @Test
    @WithMockUser(username = "orgadmin", roles = "ORG_ADMIN")
    void orgAdminCannotOpenAnotherOrganizationsDashboard() throws Exception {
        Organization userOrganization = new Organization("Demo Agency", "demo", true);
        Organization requestedOrganization = new Organization("Acme Realty", "acme", true);
        User user = new User(userOrganization, "orgadmin", "orgadmin@demo.local", "hash", "pass", UserRole.ORG_ADMIN, true);

        when(organizationRepository.findBySlugAndActiveTrue("acme"))
            .thenReturn(Optional.of(requestedOrganization));
        when(userRepository.findByUsername("orgadmin"))
            .thenReturn(Optional.of(user));

        mockMvc.perform(get("/acme/dashboard"))
            .andExpect(status().isForbidden())
            .andExpect(content().string(org.hamcrest.Matchers.containsString("Access denied")));
    }

    @Test
    @WithMockUser(username = "admin", roles = "PLATFORM_ADMIN")
    void platformAdminCanOpenAnyOrganizationDashboard() throws Exception {
        Organization organization = new Organization("Acme Realty", "acme", true);
        User admin = new User(null, "admin", "admin@ace.local", "hash", "pass", UserRole.PLATFORM_ADMIN, true);

        when(organizationRepository.findBySlugAndActiveTrue("acme"))
            .thenReturn(Optional.of(organization));
        when(userRepository.findByUsername("admin"))
            .thenReturn(Optional.of(admin));
        when(organizationRepository.findAll(org.springframework.data.domain.Sort.by(org.springframework.data.domain.Sort.Direction.ASC, "name")))
            .thenReturn(List.of(organization));
        when(userRepository.findAllByOrderByUsernameAsc())
            .thenReturn(List.of(admin));
        when(organizationRepository.count())
            .thenReturn(1L);
        when(userRepository.count())
            .thenReturn(1L);
        when(userRepository.countByOrganizationId(anyLong())).thenReturn(1L);
        when(leadService.listForOrganization(anyLong())).thenReturn(List.of());

        mockMvc.perform(get("/admin/dashboard"))
            .andExpect(status().isOk());

        mockMvc.perform(get("/acme/dashboard"))
            .andExpect(status().isOk())
            .andExpect(content().string(org.hamcrest.Matchers.containsString("Acme Realty")));
    }
}
