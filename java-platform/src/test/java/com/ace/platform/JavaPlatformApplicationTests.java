package com.ace.platform;

import com.ace.platform.organization.OrganizationRepository;
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

	@Test
	void contextLoads() {
	}

}
