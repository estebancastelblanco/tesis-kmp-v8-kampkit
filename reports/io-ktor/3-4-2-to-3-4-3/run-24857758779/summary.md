### Dependabot impact companion

- **Dependency:** `io.ktor`
- **Version change:** `3.4.2` → `3.4.3`
- **Risk:** **HIGH**
- **Recommendation:** Hold merge until impacted files are reviewed and targeted regression checks pass.
- **Static impact:** 19 files (6 direct / 13 transitive-or-expect-actual)
- **UI impact:** 18 screens
- **Dynamic analysis:** completed (3 screen diffs)
- **Full report:** generated as static artifact/site in `output/report/`

### Top impacted files

| File | Relation | Source set | RLOC | MCC |
|------|----------|------------|------|-----|
| `/tmp/output/phase1/before/shared/src/commonTest/kotlin/co/touchlab/kampkit/DogApiTest.kt` | direct | commonTest | 67 | 1 |
| `/tmp/output/phase1/before/shared/src/commonMain/kotlin/co/touchlab/kampkit/ktor/DogApiImpl.kt` | direct | commonMain | 50 | 1 |
| `/tmp/output/phase1/before/shared/src/iosMain/kotlin/co/touchlab/kampkit/KoinIOS.kt` | direct | ios | 33 | 1 |
| `/tmp/output/phase1/before/shared/src/androidMain/kotlin/co/touchlab/kampkit/KoinAndroid.kt` | direct | androidMain | 24 | 1 |
| `/tmp/output/phase1/before/tools/kmp-impact-analyzer/tests/fixtures/sample_kotlin/CommonModule.kt` | direct | common | 8 | 1 |
| `/tmp/output/phase1/before/tools/kmp-impact-analyzer/tools/kmp-impact-analyzer/tests/fixtures/sample_kotlin/CommonModule.kt` | direct | common | 8 | 1 |
| `/tmp/output/phase1/before/shared/src/commonMain/kotlin/co/touchlab/kampkit/models/BreedViewModel.kt` | transitive | commonMain | 99 | 15 |
| `/tmp/output/phase1/before/shared/src/commonTest/kotlin/co/touchlab/kampkit/BreedViewModelTest.kt` | transitive | commonTest | 249 | 9 |
| `/tmp/output/phase1/before/shared/src/commonTest/kotlin/co/touchlab/kampkit/BreedRepositoryTest.kt` | transitive | commonTest | 128 | 7 |
| `/tmp/output/phase1/before/shared/src/commonMain/kotlin/co/touchlab/kampkit/Koin.kt` | transitive | commonMain | 66 | 5 |
