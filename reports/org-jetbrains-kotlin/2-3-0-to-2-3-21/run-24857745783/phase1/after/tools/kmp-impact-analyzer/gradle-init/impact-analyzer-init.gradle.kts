/**
 * Gradle Init Script — Injects Detekt into any Kotlin/KMP project
 * without modifying build files.
 *
 * Usage:
 *   gradle --init-script gradle/impact-analyzer-init.gradle.kts detekt
 *
 * This script:
 *   1. Adds the Detekt plugin to all subprojects
 *   2. Configures Detekt to produce XML reports with complexity metrics
 *   3. Applies to both KMP and regular Kotlin projects
 */
initscript {
    repositories {
        gradlePluginPortal()
        mavenCentral()
    }
    dependencies {
        classpath("io.gitlab.arturbosch.detekt:detekt-gradle-plugin:1.23.4")
    }
}

allprojects {
    afterEvaluate {
        // Only apply to projects that have Kotlin plugin applied
        val hasKotlin = plugins.hasPlugin("org.jetbrains.kotlin.multiplatform") ||
                plugins.hasPlugin("org.jetbrains.kotlin.jvm") ||
                plugins.hasPlugin("org.jetbrains.kotlin.android") ||
                plugins.hasPlugin("kotlin-android")

        if (hasKotlin && !plugins.hasPlugin("io.gitlab.arturbosch.detekt")) {
            apply(plugin = "io.gitlab.arturbosch.detekt")

            extensions.configure<io.gitlab.arturbosch.detekt.extensions.DetektExtension> {
                buildUponDefaultConfig = true
                allRules = false
                // Generate XML report with complexity metrics
                reports {
                    xml {
                        required.set(true)
                        outputLocation.set(file("${project.buildDir}/reports/detekt/detekt.xml"))
                    }
                    html {
                        required.set(false)
                    }
                    txt {
                        required.set(false)
                    }
                    sarif {
                        required.set(false)
                    }
                }
            }

            logger.lifecycle("[impact-analyzer] Detekt injected into project: ${project.name}")
        }
    }
}
