*** Settings ***
Documentation       多进程批量栈内存监控测试用例集

Resource            ../../resources/common.robot

Suite Teardown      关闭SSH连接


*** Variables ***
${TEST_HOST}            192.168.1.100
${TEST_USER}            root
${TEST_PASSWORD}        %{SSH_PASSWORD}
${USAGE_THRESHOLD}      80.0


*** Test Cases ***
多进程批量栈内存监控测试
    [Documentation]    批量监控多个进程的栈内存使用情况
    [Tags]    stack    batch    performance
    @{PIDS}    Create List    12345    67890    13579    24680
    连接SSH服务器    ${TEST_HOST}    ${TEST_USER}    密码=${TEST_PASSWORD}
    FOR    ${pid}    IN    @{PIDS}
        采集并分析进程栈内存    ${pid}
        ${report_path}    Set Variable    ${OUTPUT_DIR}/stack_monitor/stack_report_${pid}.json
        ${status}    生成栈内存分析报告    输出文件路径=${report_path}    使用率阈值=${USAGE_THRESHOLD}
        Should Be Equal    ${status}    PASS
    END

多服务器批量监控测试
    [Documentation]    批量监控多个服务器上的进程栈内存
    [Tags]    stack    multi-server    operation
    &{SERVER1}    Create Dictionary    host=192.168.1.100    user=root    password=%{SSH_PASSWORD1}    pid=1234
    &{SERVER2}    Create Dictionary    host=192.168.1.101    user=admin    password=%{SSH_PASSWORD2}    pid=5678
    @{SERVERS}    Create List    ${SERVER1}    ${SERVER2}
    FOR    ${server}    IN    @{SERVERS}
        连接SSH服务器    ${server.host}    ${server.user}    密码=${server.password}
        采集并分析进程栈内存    ${server.pid}
        ${report_path}    Set Variable    ${OUTPUT_DIR}/stack_monitor/stack_report_${server.pid}.json
        ${status}    生成栈内存分析报告    输出文件路径=${report_path}    使用率阈值=${USAGE_THRESHOLD}
        Should Be Equal    ${status}    PASS
    END
