package com.ace.platform.config;

import com.ace.platform.organization.Organization;
import com.ace.platform.organization.OrganizationRepository;
import com.ace.platform.survey.SurveyService;
import com.ace.platform.user.User;
import com.ace.platform.user.UserRepository;
import com.ace.platform.user.UserRole;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.ApplicationRunner;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Profile;
import org.springframework.security.crypto.password.PasswordEncoder;

@Configuration
@Profile({"dev", "demo"})
public class DevDataSeeder {

    private static final Logger log = LoggerFactory.getLogger(DevDataSeeder.class);

    @Bean
    ApplicationRunner seedDefaultData(
        OrganizationRepository organizationRepository,
        UserRepository userRepository,
        PasswordEncoder passwordEncoder,
        SurveyService surveyService,
        @Value("${ace.demo.org-name:Demo Agency}") String demoOrgName,
        @Value("${ace.demo.org-slug:demo}") String demoOrgSlug,
        @Value("${ace.demo.admin-username:admin}") String demoAdminUsername,
        @Value("${ace.demo.admin-email:admin@ace.local}") String demoAdminEmail,
        @Value("${ace.demo.admin-password:test123}") String demoAdminPassword
    ) {
        return args -> {
            Organization demoOrg = organizationRepository.findBySlug(demoOrgSlug)
                .orElseGet(() -> organizationRepository.save(new Organization(demoOrgName, demoOrgSlug, true)));

            userRepository.findByUsername(demoAdminUsername).ifPresentOrElse(existingAdmin -> {
                existingAdmin.setEmail(demoAdminEmail);
                existingAdmin.setRole(UserRole.PLATFORM_ADMIN);
                existingAdmin.setActive(true);
                if (existingAdmin.getVisiblePassword() == null || existingAdmin.getVisiblePassword().isBlank()) {
                    existingAdmin.setPasswordHash(passwordEncoder.encode(demoAdminPassword));
                    existingAdmin.setVisiblePassword(demoAdminPassword);
                }
                userRepository.save(existingAdmin);
            }, () -> {
                User admin = new User(
                    null,
                    demoAdminUsername,
                    demoAdminEmail,
                    passwordEncoder.encode(demoAdminPassword),
                    demoAdminPassword,
                    UserRole.PLATFORM_ADMIN,
                    true
                );
                userRepository.save(admin);
                log.info("Seeded platform admin user: username={} password={} (demo/dev profile only)", demoAdminUsername, demoAdminPassword);
            });

            surveyService.ensureDefaultSurvey(demoOrg);
            log.info("Demo organization available at slug={} (id={})", demoOrg.getSlug(), demoOrg.getId());
        };
    }
}
