/*!
 * Licensed to the Apache Software Foundation (ASF) under one
 * or more contributor license agreements.  See the NOTICE file
 * distributed with this work for additional information
 * regarding copyright ownership.  The ASF licenses this file
 * to you under the Apache License, Version 2.0 (the
 * "License"); you may not use this file except in compliance
 * with the License.  You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing,
 * software distributed under the License is distributed on an
 * "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
 * KIND, either express or implied.  See the License for the
 * specific language governing permissions and limitations
 * under the License.
 */
import { Box, Heading, VStack } from "@chakra-ui/react";
import { useState } from "react";
import { useHotkeys } from "react-hotkeys-hook";
import { useTranslation } from "react-i18next";
import { useParams, useSearchParams } from "react-router-dom";
import { useLocalStorage } from "usehooks-ts";

import { useTaskInstanceServiceGetMappedTaskInstance } from "openapi/queries";
import { Dialog } from "src/components/ui";
import { SearchParamsKeys } from "src/constants/searchParams";
import { useConfig } from "src/queries/useConfig";
import { useLogs } from "src/queries/useLogs";

import { ExternalLogLink } from "./ExternalLogLink";
import { TaskLogContent } from "./TaskLogContent";
import { TaskLogHeader } from "./TaskLogHeader";

export const Logs = () => {
  const { dagId = "", mapIndex = "-1", runId = "", taskId = "" } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const { t: translate } = useTranslation("dag");

  const tryNumberParam = searchParams.get(SearchParamsKeys.TRY_NUMBER);
  const logLevelFilters = searchParams.getAll(SearchParamsKeys.LOG_LEVEL);
  const sourceFilters = searchParams.getAll(SearchParamsKeys.SOURCE);

  const {
    data: taskInstance,
    error,
    isLoading,
  } = useTaskInstanceServiceGetMappedTaskInstance({
    dagId,
    dagRunId: runId,
    mapIndex: parseInt(mapIndex, 10),
    taskId,
  });

  const onSelectTryNumber = (newTryNumber: number) => {
    if (newTryNumber === taskInstance?.try_number) {
      searchParams.delete(SearchParamsKeys.TRY_NUMBER);
    } else {
      searchParams.set(SearchParamsKeys.TRY_NUMBER, newTryNumber.toString());
    }
    setSearchParams(searchParams);
  };

  const tryNumber = tryNumberParam === null ? taskInstance?.try_number : parseInt(tryNumberParam, 10);

  const defaultWrap = Boolean(useConfig("default_wrap"));
  const defaultShowTimestamp = Boolean(true);

  const [wrap, setWrap] = useLocalStorage<boolean>("log_wrap", defaultWrap);
  const [showTimestamp, setShowTimestamp] = useLocalStorage<boolean>(
    "log_show_timestamp",
    defaultShowTimestamp,
  );
  const [showSource, setShowSource] = useLocalStorage<boolean>("log_show_source", true);
  const [fullscreen, setFullscreen] = useState(false);
  const [expanded, setExpanded] = useState(false);

  const toggleWrap = () => setWrap(!wrap);
  const toggleTimestamp = () => setShowTimestamp(!showTimestamp);
  const toggleSource = () => setShowSource(!showSource);
  const toggleFullscreen = () => setFullscreen(!fullscreen);
  const toggleExpanded = () => setExpanded((act) => !act);

  useHotkeys("w", toggleWrap);
  useHotkeys("f", toggleFullscreen);
  useHotkeys("e", toggleExpanded);
  useHotkeys("t", toggleTimestamp);
  useHotkeys("s", toggleSource);

  const onOpenChange = () => {
    setFullscreen(false);
  };

  const {
    data,
    error: logError,
    isLoading: isLoadingLogs,
  } = useLogs({
    dagId,
    expanded,
    logLevelFilters,
    showSource,
    showTimestamp,
    sourceFilters,
    taskInstance,
    tryNumber,
  });

  const externalLogName = useConfig("external_log_name") as string;
  const showExternalLogRedirect = Boolean(useConfig("show_external_log_redirect"));

  return (
    <Box display="flex" flexDirection="column" h="100%" p={2}>
      <TaskLogHeader
        expanded={expanded}
        onSelectTryNumber={onSelectTryNumber}
        showSource={showSource}
        showTimestamp={showTimestamp}
        sourceOptions={data.sources}
        taskInstance={taskInstance}
        toggleExpanded={toggleExpanded}
        toggleFullscreen={toggleFullscreen}
        toggleSource={toggleSource}
        toggleTimestamp={toggleTimestamp}
        toggleWrap={toggleWrap}
        tryNumber={tryNumber}
        wrap={wrap}
      />
      {showExternalLogRedirect && externalLogName && taskInstance ? (
        tryNumber === undefined ? (
          <p>{translate("logs.noTryNumber")}</p>
        ) : (
          <ExternalLogLink
            externalLogName={externalLogName}
            taskInstance={taskInstance}
            tryNumber={tryNumber}
          />
        )
      ) : undefined}
      <TaskLogContent
        error={error}
        isLoading={isLoading || isLoadingLogs}
        logError={logError}
        parsedLogs={data.parsedLogs ?? []}
        wrap={wrap}
      />
      <Dialog.Root onOpenChange={onOpenChange} open={fullscreen} scrollBehavior="inside" size="full">
        <Dialog.Content backdrop>
          <Dialog.Header>
            <VStack gap={2}>
              <Heading size="xl">{taskId}</Heading>
              <TaskLogHeader
                expanded={expanded}
                isFullscreen
                onSelectTryNumber={onSelectTryNumber}
                showSource={showSource}
                showTimestamp={showTimestamp}
                taskInstance={taskInstance}
                toggleExpanded={toggleExpanded}
                toggleFullscreen={toggleFullscreen}
                toggleSource={toggleSource}
                toggleTimestamp={toggleTimestamp}
                toggleWrap={toggleWrap}
                tryNumber={tryNumber}
                wrap={wrap}
              />
            </VStack>
          </Dialog.Header>

          <Dialog.CloseTrigger />

          <Dialog.Body display="flex" flexDirection="column">
            <TaskLogContent
              error={error}
              isLoading={isLoading || isLoadingLogs}
              logError={logError}
              parsedLogs={data.parsedLogs ?? []}
              wrap={wrap}
            />
          </Dialog.Body>
        </Dialog.Content>
      </Dialog.Root>
    </Box>
  );
};
