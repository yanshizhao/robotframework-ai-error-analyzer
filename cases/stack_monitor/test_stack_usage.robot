*** Settings ***
Documentation       远程进程栈内存监控测试用例集

Resource            ../../resources/common.robot

Suite Teardown      关闭SSH连接


*** Variables ***
${TEST_HOST}            192.168.1.100
${TEST_USER}            root
${TEST_PASSWORD}        %{SSH_PASSWORD}
${USAGE_THRESHOLD}      80.0
${TEST_PID}             pid


*** Test Cases ***
单进程栈内存使用率测试
    [Documentation]    测试指定进程栈内存使用率是否在安全范围内
    [Tags]    stack    smoke    production
    连接SSH服务器    ${TEST_HOST}    ${TEST_USER}    密码=${TEST_PASSWORD}
    采集并分析进程栈内存    ${TEST_PID}
    ${report_path}    Set Variable    ${OUTPUT_DIR}/stack_monitor/stack_report_${TEST_PID}.json
    ${status}    生成栈内存分析报告    输出文件路径=${report_path}    使用率阈值=${USAGE_THRESHOLD}
    Should Be Equal    ${status}    PASS

基于密钥认证的栈内存监控测试
    [Documentation]    使用SSH密钥认证方式进行栈内存监控
    [Tags]    stack    security    production
    连接SSH服务器    ${TEST_HOST}    ${TEST_USER}    密钥文件路径=%{SSH_KEY_PATH}
    采集并分析进程栈内存    ${TEST_PID}
    ${report_path}    Set Variable    ${OUTPUT_DIR}/stack_monitor/stack_report_${TEST_PID}.json
    ${status}    生成栈内存分析报告    输出文件路径=${report_path}    使用率阈值=${USAGE_THRESHOLD}
    Should Be Equal    ${status}    PASS
