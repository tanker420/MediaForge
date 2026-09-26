import java.util.Properties

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "cn.mediaforge.app"
    compileSdk = 34

    defaultConfig {
        applicationId = "cn.mediaforge.app"
        minSdk = 24
        targetSdk = 34
        versionCode = 140
        versionName = "1.4.0"
        ndk { abiFilters += listOf("armeabi-v7a", "arm64-v8a") }
    }

    signingConfigs {
        create("release") {
            val ks = rootProject.file("release.keystore")
            // 口令从 local.properties 读（该文件已被 .gitignore 排除，不入库）。
            // 未配置时 release 构建退化为不签名，CI 会注入签名配置。
            val lp = Properties().apply {
                val f = rootProject.file("local.properties")
                if (f.exists()) f.inputStream().use { load(it) }
            }
            val storePwd = lp.getProperty("keystore.storePassword", "")
            val keyPwd = lp.getProperty("keystore.keyPassword", "")
            val alias = lp.getProperty("keystore.keyAlias", "")
            if (ks.exists() && storePwd.isNotEmpty() && alias.isNotEmpty()) {
                storeFile = ks
                storePassword = storePwd
                keyAlias = alias
                keyPassword = keyPwd
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            val ks = rootProject.file("release.keystore")
            if (ks.exists() &&
                signingConfigs.getByName("release").storePassword?.isNotEmpty() == true) {
                signingConfig = signingConfigs.getByName("release")
            }
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }

    packaging {
        resources.excludes += setOf("META-INF/DEPENDENCIES", "META-INF/LICENSE.md", "META-INF/NOTICE.md")
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.12.0")
    implementation("androidx.appcompat:appcompat:1.6.1")
    implementation("com.google.android.material:material:1.11.0")
    implementation("androidx.recyclerview:recyclerview:1.3.2")
    implementation("com.arthenica:ffmpeg-kit-full-gpl:6.0-2")
}
