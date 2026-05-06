package com.ace.platform.user;

import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

public interface UserRepository extends JpaRepository<User, Long> {
    Optional<User> findByUsername(String username);
    Optional<User> findByEmail(String email);
    boolean existsByUsername(String username);
    boolean existsByEmail(String email);
    boolean existsByUsernameAndIdNot(String username, Long id);
    boolean existsByEmailAndIdNot(String email, Long id);
    List<User> findAllByOrderByUsernameAsc();
    List<User> findByOrganizationIdOrderByUsernameAsc(Long organizationId);
    long countByOrganizationId(Long organizationId);
    long deleteByOrganizationId(Long organizationId);
}
