*** Settings ***
Documentation    公共关键字和变量定义，所有用例均可导入使用
Library          Collections
Library          String
Library          OperatingSystem
Library          ../libs/StackMonitorKeywords.py

*** Variables ***
${DEFAULT_TIMEOUT}    10s
${RETRY_INTERVAL}     2s
${OUTPUT_DIR}         ${CURDIR}/../reports
${DATA_DIR}           ${CURDIR}/../data
${CONFIG_DIR}         ${CURDIR}/../config
${DEFAULT_STACK_THRESHOLD}    80.0

*** Keywords ***
等待并验证元素
    [Arguments]    ${locator}    ${expected_text}=${None}
    Wait Until Element Is Visible    ${locator}    timeout=${DEFAULT_TIMEOUT}
    Run Keyword If    '${expected_text}' != '${None}'
    ...    Element Text Should Be    ${locator}    ${expected_text}
