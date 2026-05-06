package com.ace.platform.organization;

import com.ace.platform.common.model.BaseEntity;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Table;

@Entity
@Table(name = "organizations")
public class Organization extends BaseEntity {

    @Column(name = "name", nullable = false, length = 200)
    private String name;

    @Column(name = "slug", nullable = false, unique = true, length = 120)
    private String slug;

    @Column(name = "active", nullable = false)
    private boolean active = true;

    protected Organization() {
    }

    public Organization(String name, String slug, boolean active) {
        this.name = name;
        this.slug = slug;
        this.active = active;
    }

    public String getName() {
        return name;
    }

    public void setName(String name) {
        this.name = name;
    }

    public String getSlug() {
        return slug;
    }

    public void setSlug(String slug) {
        this.slug = slug;
    }

    public boolean isActive() {
        return active;
    }

    public void setActive(boolean active) {
        this.active = active;
    }
}
