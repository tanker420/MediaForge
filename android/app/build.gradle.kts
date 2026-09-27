import com.android.build.gradle.api.BaseVariantOutput
import com.android.build.gradle.internal.api.ApkVariantOutputImpl
import org.gradle.api.Action

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

// 版本号单一来源：versionName 与产物文件名都从这里取
val appVersion = "1.4.2"

android {
    namespace = "cn.mediaforge.app"
    compileSdk = 34

    defaultConfig {
        applicationId = "cn.mediaforge.app"
        minSdk = 24
        targetSdk = 34
        versionCode = 142
        versionName = appVersion
        ndk { abiFilters += listOf("armeabi-v7a", "arm64-v8a") }
    }

    signingConfigs {
        create("release") {
            // 签名密钥与口令随仓库固化（release.keystore 已入库），
            // 保证本地与 CI 产出的 APK 签名完全一致，可直接覆盖升级。
            storeFile = rootProject.file("release.keystore")
            storePassword = "mediaforge"
            keyAlias = "mediaforge"
            keyPassword = "mediaforge"
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            signingConfig = signingConfigs.getByName("release")
        }
    }

    // 产物按版本号命名：MediaForge-1.4.2.apk（原先固定为 app-release.apk）。
    // 必须显式 Action，否则 Kotlin 会把 outputs.all{} 解析成 Iterable.all 谓词重载。
    applicationVariants.all {
        if (buildType.name == "release") {
            outputs.all(object : Action<BaseVariantOutput> {
                override fun execute(output: BaseVariantOutput) {
                    (output as ApkVariantOutputImpl).outputFileName =
                        "MediaForge-$appVersion.apk"
                }
            })
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
