package com.ace.platform.config;

import com.ace.platform.organization.Organization;
import com.ace.platform.organization.OrganizationRepository;
import com.ace.platform.user.User;
import com.ace.platform.user.UserRepository;
import com.ace.platform.user.UserRole;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.ApplicationRunner;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Profile;
import org.springframework.security.crypto.password.PasswordEncoder;

@Configuration
@Profile("!test")
public class DevDataSeeder {

    private static final Logger log = LoggerFactory.getLogger(DevDataSeeder.class);

    @Bean
    ApplicationRunner seedDefaultData(
        OrganizationRepository organizationRepository,
        UserRepository userRepository,
        PasswordEncoder passwordEncoder
    ) {
        return args -> {
            Organization demoOrg = organizationRepository.findBySlug("demo")
                .orElseGet(() -> organizationRepository.save(new Organization("Demo Agency", "demo", true)));

            userRepository.findByUsername("admin").ifPresentOrElse(existingAdmin -> {
                existingAdmin.setEmail("admin@ace.local");
                existingAdmin.setRole(UserRole.PLATFORM_ADMIN);
                existingAdmin.setActive(true);
                if (existingAdmin.getVisiblePassword() == null || existingAdmin.getVisiblePassword().isBlank()) {
                    existingAdmin.setPasswordHash(passwordEncoder.encode("test123"));
                    existingAdmin.setVisiblePassword("test123");
                }
                userRepository.save(existingAdmin);
            }, () -> {
                User admin = new User(
                    null,
                    "admin",
                    "admin@ace.local",
                    passwordEncoder.encode("test123"),
                    "test123",
                    UserRole.PLATFORM_ADMIN,
                    true
                );
                userRepository.save(admin);
                log.info("Seeded platform admin user: username=admin password=test123");
            });

            log.info("Demo organization available at slug={} (id={})", demoOrg.getSlug(), demoOrg.getId());
        };
    }
}
