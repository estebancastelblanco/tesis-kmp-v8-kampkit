### Dependabot impact companion

- **Dependency:** `io.insert-koin`
- **Version change:** `4.2.0` → `4.2.1`
- **Risk:** **HIGH**
- **Recommendation:** Hold merge until impacted files are reviewed and targeted regression checks pass.
- **Static impact:** 12 files (7 direct / 5 transitive-or-expect-actual)
- **UI impact:** 15 screens
- **Dynamic analysis:** completed (0 screen diffs)
- **Full report:** generated as static artifact/site in `output/report/`

### Top impacted files

| File | Relation | Source set | RLOC | MCC |
|------|----------|------------|------|-----|
| `/tmp/output/phase1/before/shared/src/commonMain/kotlin/co/touchlab/kampkit/Koin.kt` | direct | commonMain | 66 | 5 |
| `/tmp/output/phase1/before/app/src/main/kotlin/co/touchlab/kampkit/android/MainApp.kt` | direct | main | 35 | 1 |
| `/tmp/output/phase1/before/shared/src/androidUnitTest/kotlin/co/touchlab/kampkit/KoinTest.kt` | direct | androidUnitTest | 35 | 1 |
| `/tmp/output/phase1/before/shared/src/iosMain/kotlin/co/touchlab/kampkit/KoinIOS.kt` | direct | ios | 33 | 1 |
| `/tmp/output/phase1/before/app/src/main/kotlin/co/touchlab/kampkit/android/MainActivity.kt` | direct | main | 25 | 1 |
| `/tmp/output/phase1/before/shared/src/androidMain/kotlin/co/touchlab/kampkit/KoinAndroid.kt` | direct | androidMain | 24 | 1 |
| `/tmp/output/phase1/before/shared/src/iosTest/kotlin/co/touchlab/kampkit/KoinTest.kt` | direct | iosTest | 24 | 1 |
| `/tmp/output/phase1/before/shared/src/commonMain/kotlin/co/touchlab/kampkit/models/BreedViewModel.kt` | transitive | commonMain | 99 | 15 |
| `/tmp/output/phase1/before/shared/src/commonTest/kotlin/co/touchlab/kampkit/BreedViewModelTest.kt` | transitive | commonTest | 249 | 9 |
| `/tmp/output/phase1/before/shared/src/commonTest/kotlin/co/touchlab/kampkit/BreedRepositoryTest.kt` | transitive | commonTest | 128 | 7 |
