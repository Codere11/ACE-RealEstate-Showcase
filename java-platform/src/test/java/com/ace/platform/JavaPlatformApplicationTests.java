package com.ace.platform;

import com.ace.platform.chat.PublicChatService;
import com.ace.platform.chat.TakeoverService;
import com.ace.platform.conversation.ConversationMessageRepository;
import com.ace.platform.conversation.ConversationService;
import com.ace.platform.events.LeadEventRepository;
import com.ace.platform.events.LeadEventService;
import com.ace.platform.lead.LeadRepository;
import com.ace.platform.lead.LeadService;
import com.ace.platform.organization.OrganizationRepository;
import com.ace.platform.survey.SurveyService;
import com.ace.platform.user.UserRepository;
import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.test.context.ActiveProfiles;

@SpringBootTest
@ActiveProfiles("test")
class JavaPlatformApplicationTests {

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
	void contextLoads() {
	}

}
