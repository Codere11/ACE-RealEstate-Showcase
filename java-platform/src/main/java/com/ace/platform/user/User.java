package com.ace.platform.user;

import com.ace.platform.common.model.BaseEntity;
import com.ace.platform.organization.Organization;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.FetchType;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;

@Entity
@Table(name = "users")
public class User extends BaseEntity {

    @ManyToOne(fetch = FetchType.EAGER, optional = true)
    @JoinColumn(name = "organization_id")
    private Organization organization;

    @Column(name = "username", nullable = false, unique = true, length = 120)
    private String username;

    @Column(name = "email", nullable = false, unique = true, length = 255)
    private String email;

    @Column(name = "password_hash", nullable = false, length = 255)
    private String passwordHash;

    @Column(name = "visible_password", length = 255)
    private String visiblePassword;

    @Enumerated(EnumType.STRING)
    @Column(name = "role", nullable = false, length = 50)
    private UserRole role;

    @Column(name = "active", nullable = false)
    private boolean active = true;

    protected User() {
    }

    public User(Organization organization, String username, String email, String passwordHash, String visiblePassword, UserRole role, boolean active) {
        this.organization = organization;
        this.username = username;
        this.email = email;
        this.passwordHash = passwordHash;
        this.visiblePassword = visiblePassword;
        this.role = role;
        this.active = active;
    }

    public Organization getOrganization() {
        return organization;
    }

    public void setOrganization(Organization organization) {
        this.organization = organization;
    }

    public String getUsername() {
        return username;
    }

    public void setUsername(String username) {
        this.username = username;
    }

    public String getEmail() {
        return email;
    }

    public void setEmail(String email) {
        this.email = email;
    }

    public String getPasswordHash() {
        return passwordHash;
    }

    public void setPasswordHash(String passwordHash) {
        this.passwordHash = passwordHash;
    }

    public String getVisiblePassword() {
        return visiblePassword;
    }

    public void setVisiblePassword(String visiblePassword) {
        this.visiblePassword = visiblePassword;
    }

    public UserRole getRole() {
        return role;
    }

    public void setRole(UserRole role) {
        this.role = role;
    }

    public boolean isActive() {
        return active;
    }

    public void setActive(boolean active) {
        this.active = active;
    }
}
