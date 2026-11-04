# 독립 추가 플러그인 조립 계약 v1

scripts/build.py의 BUILD_CONTRACT_VERSION=1과 scripts/package.py를 재사용한다. 소비자는 공통 source의 정확한 SHA와 clean 상태를 검증한 뒤 호출한다. 공통 source는 소비자의 저장소·기능 이름을 알지 않는다.

소비자 source도 common/base/{instructions.md,skills,scripts}, adapters/<product>/{지침template,skills,scripts}, scripts 구조를 사용한다. VERSION과 source commit은 소비자 소유다. package의 기본 이름/배포 경로는 기존 제품과 동일하며, 별도 패키지는 name/repository/source_repository를 명시한다. 기본 인자를 바꾸거나 공통 산출물에 소비자 파일을 추가하지 않는다.

제품별 자체 hook은 adapters/<product>/hooks/hooks.json에 선언하고 plugin_hooks=True로 명시한 경우에만 조립한다. 없으면 hook을 등록하지 않고, opt-in 없이 선언하면 빌드를 거부한다. upstream plugin hook은 이 계약으로 자동 등록하지 않는다.

common/base/resources.toml은 schema_version=1, files 배열의 source/target으로 로컬 source 파일의 배포 위치를 명시한다. 경로 이탈·symlink·기존 대상 충돌을 거부하며 assembly.json에 hash를 포함한다. compiler를 소비자에 복제하지 않는다.

runtime에서 다른 플러그인을 이용할 때 설치 identity와 실제 skill 위치를 대조해야 한다. 조립 계약은 native 호출이나 모델 자동 선택을 보장하지 않는다. 독립 추가 플러그인 없이 공통 package 조립과 기능이 완결돼야 한다.
